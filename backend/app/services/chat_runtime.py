"""Configured model calls for task conversations."""

import ipaddress
import json
import socket
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from queue import Queue
from urllib.parse import urlsplit

import httpx
from sqlalchemy.orm import Session

from ..models import Agent, ConfigItem, Task, TaskAttachment, TaskMessage, Team
from .usage import record_usage
from .knowledge import search_chunks


class ChatConfigurationError(ValueError):
    pass


class ChatProviderError(RuntimeError):
    pass


def provider_error_detail(response: httpx.Response) -> str:
    """Return safe provider fields without echoing credentials or response bodies."""
    status = response.status_code
    hints = {
        401: 'API Key 无效或已过期',
        403: 'API Key 无权限使用该模型',
        404: 'Base URL 路径或模型名称不正确',
        429: '请求频率或额度已达上限',
    }
    hint = hints.get(status, '请检查供应商服务状态、Base URL 和模型名称')
    try:
        error = response.json().get('error')
        if isinstance(error, dict):
            code = error.get('code')
            if isinstance(code, (str, int)) and 0 < len(str(code)) <= 64 and str(code).replace('_', '').replace('-', '').isalnum():
                hint += f'（错误代码：{code}）'
    except (ValueError, AttributeError):
        pass
    return f'模型服务返回 HTTP {status}：{hint}'


def model_for_agent(db: Session, agent: Agent) -> ConfigItem:
    model = db.get(ConfigItem, agent.model_config_id) if agent.model_config_id else None
    if agent.model_config_id and not model:
        raise ChatConfigurationError(f'{agent.name} 绑定的模型已不存在')
    if not model:
        model = db.query(ConfigItem).filter(ConfigItem.category == 'models', ConfigItem.model_name == agent.model_name).first()
    if not model and not agent.model_config_id:
        model = db.query(ConfigItem).filter(ConfigItem.category == 'models', ConfigItem.is_default.is_(True), ConfigItem.status == '已启用').first()
    if not model or model.category != 'models' or model.status != '已启用':
        raise ChatConfigurationError(f'{agent.name} 没有绑定已启用的模型')
    if not model.api_key:
        raise ChatConfigurationError(f'模型「{model.name}」尚未配置 API Key')
    if not model.base_url or not model.model_name:
        raise ChatConfigurationError(f'模型「{model.name}」缺少 Base URL 或模型名称')
    return model


def agents_for_task(db: Session, task: Task) -> list[Agent]:
    if task.target_type == 'team':
        team = db.get(Team, task.team_id or task.target_id)
        if not team:
            raise ChatConfigurationError('任务关联的团队不存在')
        ids = team.agent_ids or []
        if not ids:
            raise ChatConfigurationError('团队尚未配置智能体')
    else:
        ids = (task.workflow or {}).get('agent_ids') or [task.target_id]
    if task.collaboration_mode == '流程图编排':
        nodes = (task.workflow or {}).get('nodes')
        if not isinstance(nodes, list) or not nodes:
            raise ChatConfigurationError('流程图尚未配置智能体节点')
        ordered = [node.get('agent_id') if isinstance(node, dict) else None for node in nodes]
        if any(not isinstance(agent_id, int) or isinstance(agent_id, bool) for agent_id in ordered):
            raise ChatConfigurationError('流程图包含无效的智能体节点')
        if len(ordered) != len(ids) or set(ordered) != set(ids):
            raise ChatConfigurationError('流程图节点与所选智能体不一致，请重新创建任务')
        ids = ordered
    agents = [db.get(Agent, agent_id) for agent_id in ids if agent_id]
    if not agents or any(agent is None or not agent.enabled for agent in agents):
        raise ChatConfigurationError('请为任务选择至少一个已启用的智能体')
    return agents


def system_prompt(db: Session, agent: Agent) -> str:
    prompt = (agent.prompt or '').strip()
    if agent.prompt_config_id:
        item = db.get(ConfigItem, agent.prompt_config_id)
        if item and item.category == 'prompts' and item.status == '已启用':
            prompt = (item.content or '').strip() or prompt
    if not prompt:
        prompt = f'你是{agent.name}，职责是{agent.role}。请直接回答用户的问题。'
    skills = []
    for skill_id in agent.skill_config_ids or []:
        item = db.get(ConfigItem, skill_id)
        if item and item.category == 'skills' and item.status == '已启用' and item.content:
            skills.append(f'【{item.name}】 ' + item.content[:4000])
    if skills:
        prompt += ' 可用技能说明： ' + ' '.join(skills[:5])
    return prompt


def attachment_context(db: Session, task_id: int) -> str:
    root = Path(__file__).resolve().parents[2] / 'uploads'
    notes = []
    items = db.query(TaskAttachment).filter(TaskAttachment.task_id == task_id).order_by(TaskAttachment.id.desc()).limit(5)
    for item in items:
        if Path(item.filename).suffix.lower() not in {'.txt', '.md', '.csv', '.json'}:
            continue
        path = root / item.storage_name
        if path.is_file():
            notes.append(f'【附件 {item.filename}】 ' + path.read_bytes()[:12000].decode('utf-8', errors='replace'))
    return '\n\n'.join(notes)


def knowledge_context(db: Session, task: Task, query: str) -> str:
    ids = (task.workflow or {}).get('knowledge_ids') or []
    if not isinstance(ids, list):
        return ''
    ids = list(dict.fromkeys(value for value in ids if isinstance(value, int) and not isinstance(value, bool)))[:5]
    hits = []
    for knowledge_id in ids:
        hits.extend(search_chunks(db, query, knowledge_id, limit=3))
    hits = sorted(hits, key=lambda item: item['score'], reverse=True)[:6]
    if not hits:
        return ''
    return '【知识库检索结果】\n' + '\n\n'.join(
        f"[{hit['knowledge_name']} · 文档 {hit['document_id']} · 片段 {hit['chunk_id']}] {hit['content']}"
        for hit in hits
    )


def model_request_options(model: dict) -> tuple[str, int, int]:
    base_url = str(model['base_url']).rstrip('/')
    parsed = urlsplit(base_url)
    if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password:
        raise ChatConfigurationError('模型 Base URL 无效')
    if parsed.scheme == 'http' and parsed.hostname not in {'localhost', '127.0.0.1', '::1'}:
        raise ChatConfigurationError('模型 Base URL 必须使用 HTTPS；本机地址可使用 HTTP')
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80))
    except OSError as exc:
        raise ChatProviderError('无法解析模型服务地址') from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global and parsed.hostname not in {'localhost', '127.0.0.1', '::1'}:
            raise ChatConfigurationError('模型服务地址不能指向内网或本机地址')
    url = base_url if base_url.endswith('/chat/completions') else base_url + '/chat/completions'
    options = model.get('extra') or {}
    try:
        timeout = max(5, min(180, int(options.get('timeout_seconds') or 60)))
        max_tokens = max(128, min(128000, int(options.get('max_tokens') or 3000)))
    except (TypeError, ValueError) as exc:
        raise ChatConfigurationError('模型的超时或 Token 配置无效') from exc
    return url, timeout, max_tokens


def request_model_chunks(model: dict, messages: list[dict], temperature: float, source='task', task_id=None):
    url, timeout, max_tokens = model_request_options(model)
    usage = None
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False) as client:
            with client.stream(
                'POST', url,
                headers={'Authorization': f"Bearer {model['api_key']}", 'Content-Type': 'application/json'},
                json={'model': model['model_name'], 'messages': messages, 'temperature': temperature,
                      'max_tokens': max_tokens, 'stream': True, 'stream_options': {'include_usage': True}},
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line.startswith('data:'):
                        continue
                    payload = line[5:].strip()
                    if payload == '[DONE]':
                        break
                    if not payload:
                        continue
                    data = json.loads(payload)
                    if isinstance(data.get('usage'), dict):
                        usage = data['usage']
                    choices = data.get('choices') or []
                    if choices:
                        delta = choices[0].get('delta') or {}
                        content = delta.get('content') or ''
                        if isinstance(content, list):
                            content = ''.join(part.get('text', '') for part in content if isinstance(part, dict))
                        if content:
                            yield str(content)
                record_usage(model, usage, source, task_id)
    except httpx.HTTPStatusError as exc:
        raise ChatProviderError(provider_error_detail(exc.response)) from exc
    except httpx.TimeoutException as exc:
        raise ChatProviderError(f'连接模型服务超时（{timeout} 秒），请检查网络、Base URL 或调大超时时间') from exc
    except httpx.ConnectError as exc:
        raise ChatProviderError('无法建立到模型服务的连接，请检查服务器网络、防火墙及 Base URL') from exc
    except httpx.HTTPError as exc:
        raise ChatProviderError('模型服务请求失败，请检查网络、TLS 证书及 Base URL') from exc
    except ValueError as exc:
        raise ChatProviderError('模型服务返回了无效的 JSON 响应，请检查接口是否兼容 OpenAI Chat Completions') from exc


def request_model(model: dict, messages: list[dict], temperature: float, source='task', task_id=None,
                  require_complete=False) -> str:
    url, timeout, max_tokens = model_request_options(model)
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False) as client:
            response = client.post(
                url,
                headers={'Authorization': f"Bearer {model['api_key']}", 'Content-Type': 'application/json'},
                json={'model': model['model_name'], 'messages': messages, 'temperature': temperature, 'max_tokens': max_tokens},
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ChatProviderError('模型服务返回的响应结构无效')
            record_usage(model, data.get('usage'), source, task_id)
    except httpx.HTTPStatusError as exc:
        raise ChatProviderError(provider_error_detail(exc.response)) from exc
    except httpx.TimeoutException as exc:
        raise ChatProviderError(f'连接模型服务超时（{timeout} 秒），请检查网络、Base URL 或调大超时时间') from exc
    except httpx.ConnectError as exc:
        raise ChatProviderError('无法建立到模型服务的连接，请检查服务器网络、防火墙及 Base URL') from exc
    except httpx.HTTPError as exc:
        raise ChatProviderError('模型服务请求失败，请检查网络、TLS 证书及 Base URL') from exc
    except ValueError as exc:
        raise ChatProviderError('模型服务返回了无效的 JSON 响应，请检查接口是否兼容 OpenAI Chat Completions') from exc
    choices = data.get('choices')
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise ChatProviderError('模型服务返回的响应结构无效')
    if require_complete and choices[0].get('finish_reason') not in {'stop', 'end_turn'}:
        raise ChatProviderError('模型输出未正常结束，应用代码可能被截断；请重试或调高模型输出 Token 上限')
    try:
        content = data['choices'][0]['message']['content']
        if isinstance(content, list):
            content = ''.join(part.get('text', '') for part in content if isinstance(part, dict))
        content = str(content or '').strip()
    except (KeyError, IndexError, TypeError):
        content = ''
    if not content:
        raise ChatProviderError('模型返回了空回复')
    return content


def test_model(model: ConfigItem, override_key: str = '') -> dict:
    key = override_key or model.api_key
    if not key:
        raise ChatConfigurationError('请先配置 API Key')
    content = request_model(
        {'id': model.id, 'provider': model.provider, 'base_url': model.base_url, 'model_name': model.model_name,
         'api_key': key, 'extra': (model.extra or {}) | {'timeout_seconds': 30, 'max_tokens': 128}},
        [{'role': 'user', 'content': '请只回复 OK'}], 0, source='test',
    )
    return {'ok': True, 'model': model.model_name, 'response': content[:200]}


def run_task_turn(db: Session, task: Task, user_message: TaskMessage) -> list[TaskMessage]:
    if (task.workflow or {}).get('app_mode'):
        from .app_builder import build_app_turn
        list(build_app_turn(db, task, user_message))
        return db.query(TaskMessage).filter(TaskMessage.task_id == task.id, TaskMessage.id > user_message.id).order_by(TaskMessage.id).all()
    agents = agents_for_task(db, task)
    configs = [(agent, model_for_agent(db, agent), system_prompt(db, agent)) for agent in agents]
    history = db.query(TaskMessage).filter(TaskMessage.task_id == task.id, TaskMessage.id <= user_message.id).order_by(TaskMessage.id).all()[-24:]
    conversation = [
        {'role': message.role, 'content': message.content}
        for message in history if message.role in {'user', 'assistant'} and message.content.strip()
    ]
    if not conversation or conversation[-1]['role'] != 'user':
        raise ChatConfigurationError('请先发送一条消息')
    context = '\n\n'.join(part for part in (
        attachment_context(db, task.id), knowledge_context(db, task, conversation[-1]['content'])
    ) if part)
    if context:
        conversation[-1] = {**conversation[-1], 'content': conversation[-1]['content'] + '\n\n' + context}

    def invoke(entry, prior):
        agent, model, prompt = entry
        content = request_model(
            {'id': model.id, 'provider': model.provider, 'base_url': model.base_url, 'model_name': model.model_name,
             'api_key': model.api_key, 'extra': model.extra},
            [{'role': 'system', 'content': prompt}, *prior], max(0, min(2, agent.temperature)), task_id=task.id,
        )
        return agent.name, content

    if task.collaboration_mode == '并行' and len(configs) > 1:
        with ThreadPoolExecutor(max_workers=min(4, len(configs))) as pool:
            results = list(pool.map(lambda entry: invoke(entry, conversation), configs))
    else:
        results = []
        peer_context = list(conversation)
        for entry in configs:
            name, answer = invoke(entry, peer_context)
            results.append((name, answer))
            if len(configs) > 1:
                peer_context = [*conversation, {'role': 'assistant', 'content': f'【{name}】{answer}'}]

    replies = [TaskMessage(task_id=task.id, role='assistant', agent_name=name, content=answer) for name, answer in results]
    db.add_all(replies)
    task.status = '进行中'
    task.progress = max(task.progress, 5)
    task.result = ''
    db.commit()
    for reply in replies:
        db.refresh(reply)
    return replies


def stream_task_turn(db: Session, task: Task, user_message: TaskMessage):
    """Yield agent deltas and persist replies only after every agent succeeds."""
    if (task.workflow or {}).get('app_mode'):
        from .app_builder import build_app_turn
        yield from build_app_turn(db, task, user_message)
        return
    agents = agents_for_task(db, task)
    configs = [(agent, model_for_agent(db, agent), system_prompt(db, agent)) for agent in agents]
    history = db.query(TaskMessage).filter(TaskMessage.task_id == task.id, TaskMessage.id <= user_message.id).order_by(TaskMessage.id).all()[-24:]
    conversation = [
        {'role': message.role, 'content': message.content}
        for message in history if message.role in {'user', 'assistant'} and message.content.strip()
    ]
    if not conversation or conversation[-1]['role'] != 'user':
        raise ChatConfigurationError('请先发送一条消息')
    context = '\n\n'.join(part for part in (
        attachment_context(db, task.id), knowledge_context(db, task, conversation[-1]['content'])
    ) if part)
    if context:
        conversation[-1] = {**conversation[-1], 'content': conversation[-1]['content'] + '\n\n' + context}

    def chunks(entry, prior):
        agent, model, prompt = entry
        return request_model_chunks(
            {'id': model.id, 'provider': model.provider, 'base_url': model.base_url, 'model_name': model.model_name,
             'api_key': model.api_key, 'extra': model.extra},
            [{'role': 'system', 'content': prompt}, *prior], max(0, min(2, agent.temperature)), task_id=task.id,
        )

    results = [''] * len(configs)
    if task.collaboration_mode == '并行' and len(configs) > 1:
        events = Queue()

        def worker(index, entry):
            try:
                for chunk in chunks(entry, conversation):
                    events.put(('delta', index, chunk))
            except Exception as exc:
                events.put(('error', index, exc))
            finally:
                events.put(('finished', index, None))

        with ThreadPoolExecutor(max_workers=min(4, len(configs))) as pool:
            for index, entry in enumerate(configs):
                pool.submit(worker, index, entry)
            finished = 0
            error = None
            while finished < len(configs):
                kind, index, value = events.get()
                if kind == 'finished':
                    finished += 1
                elif kind == 'error':
                    error = error or value
                elif error is None:
                    results[index] += value
                    yield {'type': 'delta', 'agent_index': index, 'agent_name': configs[index][0].name, 'content': value}
            if error:
                raise error
    else:
        peer_context = list(conversation)
        for index, entry in enumerate(configs):
            for chunk in chunks(entry, peer_context):
                results[index] += chunk
                yield {'type': 'delta', 'agent_index': index, 'agent_name': entry[0].name, 'content': chunk}
            if not results[index].strip():
                raise ChatProviderError('模型返回了空回复')
            if len(configs) > 1:
                peer_context = [*conversation, {'role': 'assistant', 'content': f'【{entry[0].name}】{results[index]}'}]

    if any(not result.strip() for result in results):
        raise ChatProviderError('模型返回了空回复')
    replies = [TaskMessage(task_id=task.id, role='assistant', agent_name=entry[0].name, content=results[index].strip())
               for index, entry in enumerate(configs)]
    db.add_all(replies)
    task.status = '进行中'
    task.progress = max(task.progress, 5)
    task.result = ''
    db.commit()
    for index, reply in enumerate(replies):
        db.refresh(reply)
        yield {'type': 'message', 'agent_index': index,
               'message': {column.name: getattr(reply, column.name) for column in reply.__table__.columns}}
    yield {'type': 'done'}
