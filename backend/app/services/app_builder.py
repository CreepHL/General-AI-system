"""Build versioned, self-contained browser apps from a conversation."""

import json
import shutil
import subprocess
import tempfile
from html.parser import HTMLParser
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import AppArtifact, ConfigItem, Task, TaskMessage
from .chat_runtime import (
    ChatConfigurationError, ChatProviderError, agents_for_task, attachment_context, knowledge_context, model_for_agent,
    request_model, system_prompt,
)


class AppValidationError(ValueError):
    pass


class AppMarkup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = 0
        self.forbidden = set()
        self.open_tags = []
        self.invalid_nesting = False

    def handle_starttag(self, tag, attrs):
        self.elements += 1
        if tag in {'script', 'style', 'iframe', 'object', 'embed', 'base', 'link', 'meta'}:
            self.forbidden.add(tag)
        if tag not in {'area', 'br', 'col', 'hr', 'img', 'input', 'source', 'track', 'wbr'}:
            self.open_tags.append(tag)
        for name, _ in attrs:
            if name.startswith('on'):
                self.forbidden.add('inline event handler')

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.open_tags and self.open_tags[-1] == tag:
            self.open_tags.pop()

    def handle_endtag(self, tag):
        if not self.open_tags or self.open_tags[-1] != tag:
            self.invalid_nesting = True
        else:
            self.open_tags.pop()


def parse_app_response(raw: str) -> dict:
    text = raw.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
    try:
        spec = json.loads(text)
    except (ValueError, TypeError) as exc:
        raise AppValidationError('模型没有返回完整的应用文件，无法展示预览') from exc
    if not isinstance(spec, dict):
        raise AppValidationError('模型返回的应用格式无效')
    title = spec.get('title')
    html = spec.get('html')
    css = spec.get('css')
    javascript = spec.get('javascript')
    reply = spec.get('reply', '')
    if any(not isinstance(value, str) for value in (title, html, css, javascript)):
        raise AppValidationError('应用缺少 HTML、CSS 或 JavaScript 文件')
    if not title.strip() or not html.strip() or not css.strip() or not javascript.strip():
        raise AppValidationError('应用文件为空，无法展示可操作预览')
    if len(title) > 200 or any(len(value) > 50000 for value in (html, css, javascript)):
        raise AppValidationError('应用文件超出大小限制，请缩小生成范围')
    if not isinstance(reply, str) or len(reply) > 3000:
        raise AppValidationError('模型返回的对话说明格式无效')
    markup = AppMarkup()
    markup.feed(html)
    markup.close()
    if markup.elements < 1 or markup.forbidden:
        raise AppValidationError('应用 HTML 包含不支持的标签或内联事件')
    if markup.open_tags or markup.invalid_nesting:
        raise AppValidationError('应用 HTML 标签未完整闭合')
    if '</script' in javascript.lower() or '</style' in css.lower():
        raise AppValidationError('应用代码包含不安全的嵌入片段')
    node = shutil.which('node')
    if not node:
        raise AppValidationError('服务器缺少 Node.js，无法校验应用 JavaScript')
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / 'app.js'
        source.write_text(javascript, encoding='utf-8')
        try:
            check = subprocess.run([node, '--check', str(source)], capture_output=True,
                                   text=True, timeout=5, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AppValidationError('JavaScript 语法检查未完成') from exc
    if check.returncode != 0:
        raise AppValidationError('JavaScript 语法检查失败，请重试生成')
    return {'title': title.strip(), 'html': html, 'css': css, 'javascript': javascript,
            'reply': reply.strip()}


SYSTEM_INSTRUCTIONS = """你是单页 Web 应用构建器。输出且只输出一个完整 JSON 对象，五个字符串字段：
title、html、css、javascript、reply。html 仅包含 body 内的实际应用界面结构，不含 script/style/iframe/link；
css 是完整样式，javascript 是完整的原生浏览器 JavaScript，使用 addEventListener 绑定交互。
reply 是给用户看的对话回复：具体列出本轮实现的交互、数据保存方式和未实现的能力。
不要把道歉、架构限制、实现解释或开发说明写到 html 页面里；这些内容只放在 reply。
必须生成可实际操作的应用，不能只展示代码、按钮占位、伪功能或省略号。
不得使用外部依赖、远程 API、外部图片或 CDN；在浏览器隔离预览中运行。
如需保存用户数据，使用平台提供的服务端存储：window.appStore.get(key) 同步读取启动时的快照，
await window.appStore.set(key, value) 异步保存到平台数据库，值须可 JSON 序列化；保存失败时在应用中提示且不要假装成功。
页面启动时即可读取快照，不能一直等待不存在的网络请求。不要直接访问 localStorage、fetch 或任意远程 API。
此存储只提供按任务隔离的 JSON 键值持久化，不提供任意后端路由、账号体系或第三方服务。
代码务必闭合、简洁，包含创建/修改需求涉及的所有交互。对已有应用的修改必须保留原有功能。
不要使用 Markdown 代码块。"""


CONTRIBUTOR_INSTRUCTIONS = """你正在参与单页网页应用构建。请根据自己的角色给出本轮具体贡献，
包括需求/交互/数据约定、边界情况与给前端实现者的明确建议。平台已有按任务隔离的 JSON 键值服务端存储，
前端可通过 window.appStore.get(key) 同步读取、await window.appStore.set(key,value) 异步保存。
这里没有任意生成并部署后端路由的能力。你当前只提供可见的设计或实现建议，
不要声称已修改文件、调用工具、运行测试或部署服务。答复简洁，便于在对话中展示。"""


def agent_details(db: Session, agent, model: ConfigItem, context_sources: list[str]) -> dict:
    def names(ids, category):
        return [item.name for item_id in ids or [] if (item := db.get(ConfigItem, item_id))
                and item.category == category and item.status == '已启用'
                and (category != 'skills' or item.content)]
    prompt = db.get(ConfigItem, agent.prompt_config_id) if agent.prompt_config_id else None
    return {'role': agent.role, 'model': model.name, 'model_name': model.model_name,
            'prompt': ((prompt.name + (' + 补充指令' if agent.prompt else ''))
                       if prompt and prompt.category == 'prompts' and prompt.status == '已启用' and (prompt.content or '').strip()
                       else ('自定义指令' if agent.prompt else '默认职责')),
            'skills': names(agent.skill_config_ids, 'skills'),
            'tools': names(agent.tool_config_ids, 'tools'), 'tools_executed': False,
            'context_sources': context_sources}


def configured_model(config: ConfigItem, *, builder: bool) -> dict:
    options = config.extra or {}
    try:
        max_tokens = max(8000 if builder else 1200, int(options.get('max_tokens') or 0))
        timeout_seconds = options.get('timeout_seconds')
        if timeout_seconds is None or timeout_seconds == '':
            timeout_seconds = 120 if builder else 60
    except (TypeError, ValueError) as exc:
        raise ChatConfigurationError('模型的超时或 Token 配置无效') from exc
    return {'id': config.id, 'provider': config.provider, 'base_url': config.base_url,
            'model_name': config.model_name, 'api_key': config.api_key,
            'extra': {**options, 'max_tokens': max_tokens, 'timeout_seconds': timeout_seconds}}


def latest_artifact(db: Session, task_id: int) -> AppArtifact | None:
    return db.query(AppArtifact).filter(AppArtifact.task_id == task_id).order_by(AppArtifact.version.desc()).first()


def build_app_turn(db: Session, task: Task, user_message: TaskMessage):
    try:
        if not (task.workflow or {}).get('app_mode'):
            raise ChatConfigurationError('该任务不是应用构建任务')
        agents = agents_for_task(db, task)
        builder = next((agent for agent in agents if '前端' in agent.role or '前端' in agent.name or '网页' in agent.role), agents[0])
        ordered_agents = (agents if task.collaboration_mode == '流程图编排' else
                          [agent for agent in agents if agent.id != builder.id] + [builder])
        configs = [(agent, model_for_agent(db, agent), system_prompt(db, agent)) for agent in ordered_agents]
        previous = latest_artifact(db, task.id)
        if previous:
            prior = json.dumps({
                'title': previous.title, 'html': previous.html, 'css': previous.css,
                'javascript': previous.javascript,
            }, ensure_ascii=False)
            if len(prior) > 80000:
                raise ChatProviderError('现有应用太大，无法安全地带入下一轮修改')
            prompt = f'当前已发布应用（必须保留已有功能）：\n{prior}\n\n本轮修改要求：\n{user_message.content}'
        else:
            prompt = f'请构建可操作的应用。用户需求：\n{user_message.content}'
        history = db.query(TaskMessage).filter(TaskMessage.task_id == task.id, TaskMessage.role == 'user').order_by(TaskMessage.id).all()
        history_text = '\n'.join(message.content for message in history if message.content.strip())[-12000:]
        attachment = attachment_context(db, task.id)
        knowledge = knowledge_context(db, task, user_message.content)
        context_sources = (['文本附件'] if attachment else []) + (['知识库检索'] if knowledge else [])
        context = '\n\n'.join(part for part in (attachment, knowledge) if part)
        if history_text:
            prompt += '\n\n历史用户需求：\n' + history_text
        if context:
            prompt += '\n\n' + context
        task.status = '正在生成应用'
        task.progress = 0
        task.result = ''
        db.commit()
        yield {'type': 'status', 'status': task.status}
        contributions = []
        results = []
        spec = None
        for index, (agent, config, instructions) in enumerate(configs):
            yield {'type': 'status', 'status': f'正在执行 {agent.name}'}
            peer_notes = ('\n\n之前智能体的实际建议：\n' +
                '\n'.join(f'【{name}】{answer}' for name, answer in contributions)[-16000:] if contributions else '')
            if agent.id == builder.id:
                content = request_model(
                    configured_model(config, builder=True), [
                        {'role': 'system', 'content': SYSTEM_INSTRUCTIONS + '\n智能体职责：' + instructions},
                        {'role': 'user', 'content': prompt + peer_notes},
                    ], max(0, min(1, agent.temperature)), source='app', task_id=task.id,
                    require_complete=True,
                )
                spec = parse_app_response(content)
                results.append(None)
                yield {'type': 'delta', 'agent_index': index, 'agent_name': agent.name,
                       'content': '应用代码已生成，等待协作结果。\n' + (spec['reply'] or '应用界面和交互代码已生成。')}
            else:
                generated = ('\n\n本轮前端已生成的代码（内容可能截断，请提供基于代码的建议，不得声称已执行）：\n' +
                    json.dumps({key: spec[key] for key in ('title', 'html', 'css', 'javascript')}, ensure_ascii=False)[:60000]
                    if spec else '')
                content = request_model(
                    configured_model(config, builder=False), [
                        {'role': 'system', 'content': CONTRIBUTOR_INSTRUCTIONS + '\n智能体职责：' + instructions},
                        {'role': 'user', 'content': prompt + peer_notes + generated},
                    ], max(0, min(1, agent.temperature)), source='app', task_id=task.id,
                )
                contributions.append((agent.name, content))
                results.append(content)
                yield {'type': 'delta', 'agent_index': index, 'agent_name': agent.name, 'content': content}
    except (ChatConfigurationError, ChatProviderError, AppValidationError, ValueError) as exc:
        task.status = '生成失败'
        task.progress = 0
        task.result = str(exc)[:500]
        db.commit()
        raise ChatProviderError(str(exc)) from exc
    version = (previous.version if previous else 0) + 1
    reply_text = spec.pop('reply') or '应用界面和交互代码已生成。'
    artifact = AppArtifact(task_id=task.id, version=version, **spec)
    replies = [TaskMessage(task_id=task.id, role='assistant', agent_name=agent.name,
                content=results[index] if results[index] is not None else f'应用版本 v{version} 已生成。\n{reply_text}',
                details=agent_details(db, agent, config, context_sources))
               for index, (agent, config, _) in enumerate(configs)]
    db.add_all([artifact, *replies])
    task.status = '可预览'
    task.progress = 100
    task.result = ''
    db.commit()
    db.refresh(artifact)
    for reply in replies:
        db.refresh(reply)
    yield {'type': 'artifact', 'artifact': {
        'id': artifact.id, 'task_id': task.id, 'version': version, **spec,
    }}
    for index, reply in enumerate(replies):
        yield {'type': 'message', 'agent_index': index,
               'message': {column.name: getattr(reply, column.name) for column in reply.__table__.columns}}
    yield {'type': 'done'}
