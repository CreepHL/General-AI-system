"""Build versioned, self-contained browser apps from a conversation."""

import json
import shutil
import subprocess
import tempfile
from html.parser import HTMLParser
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import AppArtifact, Task, TaskMessage
from .chat_runtime import (
    ChatConfigurationError, ChatProviderError, agents_for_task, model_for_agent,
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
    if any(not isinstance(value, str) for value in (title, html, css, javascript)):
        raise AppValidationError('应用缺少 HTML、CSS 或 JavaScript 文件')
    if not title.strip() or not html.strip() or not css.strip() or not javascript.strip():
        raise AppValidationError('应用文件为空，无法展示可操作预览')
    if len(title) > 200 or any(len(value) > 50000 for value in (html, css, javascript)):
        raise AppValidationError('应用文件超出大小限制，请缩小生成范围')
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
    return {'title': title.strip(), 'html': html, 'css': css, 'javascript': javascript}


SYSTEM_INSTRUCTIONS = """你是单页 Web 应用构建器。输出且只输出一个完整 JSON 对象，四个字符串字段：
title、html、css、javascript。html 仅包含 body 内的界面结构，不含 script/style/iframe/link；
css 是完整样式，javascript 是完整的原生浏览器 JavaScript，使用 addEventListener 绑定交互。
必须生成可实际操作的应用，不能只展示代码、按钮占位、伪功能或省略号。
不得使用外部依赖、远程 API、外部图片或 CDN；在浏览器隔离预览中运行。
如需保存用户数据，使用 window.appStore.get(key) 和 window.appStore.set(key, value)，值须可 JSON 序列化。
代码务必闭合、简洁，包含创建/修改需求涉及的所有交互。对已有应用的修改必须保留原有功能。
不要使用 Markdown 代码块，也不要解释。"""


def latest_artifact(db: Session, task_id: int) -> AppArtifact | None:
    return db.query(AppArtifact).filter(AppArtifact.task_id == task_id).order_by(AppArtifact.version.desc()).first()


def build_app_turn(db: Session, task: Task, user_message: TaskMessage):
    try:
        if not (task.workflow or {}).get('app_mode'):
            raise ChatConfigurationError('该任务不是应用构建任务')
        agents = agents_for_task(db, task)
        builder = agents[0]
        config = model_for_agent(db, builder)
        previous = latest_artifact(db, task.id)
        options = config.extra or {}
        try:
            max_tokens = max(8000, int(options.get('max_tokens') or 0))
            timeout_seconds = max(120, int(options.get('timeout_seconds') or 0))
        except (TypeError, ValueError) as exc:
            raise ChatConfigurationError('模型的超时或 Token 配置无效') from exc
        model = {
            'id': config.id, 'provider': config.provider, 'base_url': config.base_url,
            'model_name': config.model_name, 'api_key': config.api_key,
            'extra': {**options, 'max_tokens': max_tokens, 'timeout_seconds': timeout_seconds},
        }
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
        task.status = '正在生成应用'
        task.progress = 0
        task.result = ''
        db.commit()
        yield {'type': 'status', 'status': task.status}
        content = request_model(
            model, [
                {'role': 'system', 'content': SYSTEM_INSTRUCTIONS + '\n智能体职责：' + system_prompt(db, builder)},
                {'role': 'user', 'content': prompt},
            ], max(0, min(1, builder.temperature)), source='app', task_id=task.id,
            require_complete=True,
        )
        spec = parse_app_response(content)
    except (ChatConfigurationError, ChatProviderError, AppValidationError, ValueError) as exc:
        task.status = '生成失败'
        task.progress = 0
        task.result = str(exc)[:500]
        db.commit()
        raise ChatProviderError(str(exc)) from exc
    version = (previous.version if previous else 0) + 1
    artifact = AppArtifact(task_id=task.id, version=version, **spec)
    reply = TaskMessage(task_id=task.id, role='assistant', agent_name=builder.name,
                        content=f'应用版本 v{version} 已生成。请在右侧预览中操作；如需修改，继续发送要求。')
    db.add_all([artifact, reply])
    task.status = '可预览'
    task.progress = 100
    task.result = ''
    db.commit()
    db.refresh(artifact)
    db.refresh(reply)
    yield {'type': 'artifact', 'artifact': {
        'id': artifact.id, 'task_id': task.id, 'version': version, **spec,
    }}
    yield {'type': 'message', 'agent_index': 0,
           'message': {column.name: getattr(reply, column.name) for column in reply.__table__.columns}}
    yield {'type': 'done'}
