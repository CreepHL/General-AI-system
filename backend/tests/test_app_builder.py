import asyncio
import json
import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Agent, AppArtifact, ConfigItem, Task, TaskMessage
from app.routers.core import rebuild_task_app_stream, restore_task_app_version
from app.services.app_builder import AppValidationError, build_app_turn, parse_app_response
from app.services.chat_runtime import ChatProviderError, request_model


def app_response(title, button):
    return json.dumps({
        'title': title,
        'html': f'<main><button id="action">{button}</button><output id="result"></output></main>',
        'css': 'button { color: blue; }',
        'javascript': 'document.getElementById("action").addEventListener("click", () => { document.getElementById("result").textContent = "ok"; });',
    })


class AppBuilderTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        config = ConfigItem(category='models', name='Mock', model_name='mock', base_url='https://example.com/v1', api_key='test')
        self.db.add(config)
        self.db.flush()
        agent = Agent(name='Builder', model_config_id=config.id)
        self.db.add(agent)
        self.db.flush()
        self.task = Task(title='Calculator', target_type='agent', target_id=agent.id, workflow={'app_mode': True, 'agent_ids': [agent.id]})
        self.db.add(self.task)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def turn(self, request, response):
        message = TaskMessage(task_id=self.task.id, role='user', content=request)
        self.db.add(message)
        self.db.commit()
        with patch('app.services.app_builder.request_model', return_value=response) as model:
            events = list(build_app_turn(self.db, self.task, message))
        return events, model.call_args

    def test_create_modify_and_restore(self):
        first, _ = self.turn('做一个计算器', app_response('Calculator', '计算'))
        self.assertEqual([event['type'] for event in first], ['status', 'artifact', 'message', 'done'])
        self.assertEqual(first[1]['artifact']['version'], 1)
        self.assertEqual(self.task.status, '可预览')

        second, call = self.turn('增加一个清空按钮', app_response('Calculator Plus', '计算和清空'))
        self.assertIn('Calculator', call.args[1][1]['content'])
        self.assertIn('清空按钮', call.args[1][1]['content'])
        self.assertEqual(second[1]['artifact']['version'], 2)
        self.assertEqual(self.db.query(AppArtifact).filter_by(task_id=self.task.id).count(), 2)

        restored = restore_task_app_version(self.task.id, 1, self.db)
        self.assertEqual(restored['version'], 3)
        self.assertEqual(restored['title'], 'Calculator')
        self.assertEqual(self.task.status, '可预览')

    def test_failed_revision_keeps_previous(self):
        self.turn('初版', app_response('Working', 'Go'))
        message = TaskMessage(task_id=self.task.id, role='user', content='修改')
        self.db.add(message)
        self.db.commit()
        with patch('app.services.app_builder.request_model', side_effect=ChatProviderError('模型输出未正常结束')):
            with self.assertRaises(ChatProviderError):
                list(build_app_turn(self.db, self.task, message))
        self.assertEqual(self.task.status, '生成失败')
        self.assertEqual(self.db.query(AppArtifact).filter_by(task_id=self.task.id).count(), 1)
        self.assertEqual(self.db.query(AppArtifact).filter_by(task_id=self.task.id).first().title, 'Working')

    def test_invalid_generated_code_is_not_published(self):
        message = TaskMessage(task_id=self.task.id, role='user', content='新应用')
        self.db.add(message)
        self.db.commit()
        broken = json.dumps({'title': 'Broken', 'html': '<button>Go</button>', 'css': 'button{}', 'javascript': 'function ('})
        with patch('app.services.app_builder.request_model', return_value=broken):
            with self.assertRaises(ChatProviderError):
                list(build_app_turn(self.db, self.task, message))
        self.assertEqual(self.task.status, '生成失败')
        self.assertEqual(self.db.query(AppArtifact).filter_by(task_id=self.task.id).count(), 0)

    def test_rejects_incomplete_files(self):
        with self.assertRaises(AppValidationError):
            parse_app_response('{"title":"cut off"')
        with self.assertRaises(AppValidationError):
            parse_app_response(app_response('Bad', 'Go').replace('</main>', ''))
        with self.assertRaises(AppValidationError):
            parse_app_response(json.dumps({'title': 'Bad', 'html': '<button onclick="evil()">Go</button>', 'css': 'a{}', 'javascript': 'alert(1)'}))

    def test_rebuild_legacy_task_preserves_messages_and_uses_all_requests(self):
        self.task.workflow = {'agent_ids': [self.task.target_id]}
        self.task.status = '进行中'
        original = [
            TaskMessage(task_id=self.task.id, role='user', content='做一个费用记录网页'),
            TaskMessage(task_id=self.task.id, role='assistant', content='旧版 HTML 代码'),
            TaskMessage(task_id=self.task.id, role='user', content='刷新后记录不丢失'),
            TaskMessage(task_id=self.task.id, role='assistant', content='旧版修改代码'),
        ]
        original_contents = [item.content for item in original]
        self.db.add_all(original)
        self.db.commit()

        async def read_stream(response):
            return ''.join(part.decode() if isinstance(part, bytes) else part
                           for part in [chunk async for chunk in response.body_iterator])

        with patch('app.services.app_builder.request_model', return_value=app_response('Expenses', 'Add')) as model:
            output = asyncio.run(read_stream(rebuild_task_app_stream(self.task.id, self.db)))

        self.assertIn('"type": "artifact"', output)
        self.assertIn('做一个费用记录网页', model.call_args.args[1][1]['content'])
        self.assertIn('刷新后记录不丢失', model.call_args.args[1][1]['content'])
        self.db.refresh(self.task)
        self.assertTrue(self.task.workflow['app_mode'])
        self.assertEqual(self.task.status, '可预览')
        self.assertEqual([item.content for item in self.db.query(TaskMessage).filter_by(task_id=self.task.id).order_by(TaskMessage.id).all()[:4]],
                         original_contents)
        self.assertEqual(self.db.query(AppArtifact).filter_by(task_id=self.task.id).count(), 1)

    def test_failed_legacy_rebuild_can_be_retried(self):
        self.task.workflow = {'agent_ids': [self.task.target_id]}
        self.db.add_all([
            TaskMessage(task_id=self.task.id, role='user', content='做一个费用工具'),
            TaskMessage(task_id=self.task.id, role='assistant', content='旧回复'),
        ])
        self.db.commit()

        async def read_stream(response):
            return ''.join(part.decode() if isinstance(part, bytes) else part
                           for part in [chunk async for chunk in response.body_iterator])

        with patch('app.services.app_builder.request_model', side_effect=ChatProviderError('模型暂时不可用')):
            failed = asyncio.run(read_stream(rebuild_task_app_stream(self.task.id, self.db)))
        self.db.refresh(self.task)
        self.assertIn('"type": "error"', failed)
        self.assertEqual(self.task.status, '生成失败')
        self.assertEqual(self.db.query(AppArtifact).filter_by(task_id=self.task.id).count(), 0)

        with patch('app.services.app_builder.request_model', return_value=app_response('Expenses', 'Add')):
            retried = asyncio.run(read_stream(rebuild_task_app_stream(self.task.id, self.db)))
        self.db.refresh(self.task)
        self.assertIn('"type": "artifact"', retried)
        self.assertEqual(self.task.status, '可预览')
        self.assertEqual(self.db.query(TaskMessage).filter_by(task_id=self.task.id).count(), 3)

    def test_rebuild_uses_description_when_legacy_task_has_no_messages(self):
        self.task.workflow = {}
        self.task.description = '做一个简单的费用工具'
        self.db.commit()

        async def read_stream(response):
            return ''.join(part.decode() if isinstance(part, bytes) else part
                           for part in [chunk async for chunk in response.body_iterator])

        with patch('app.services.app_builder.request_model', return_value=app_response('Expenses', 'Add')) as model:
            output = asyncio.run(read_stream(rebuild_task_app_stream(self.task.id, self.db)))
        self.assertIn('"type": "artifact"', output)
        self.assertIn('做一个简单的费用工具', model.call_args.args[1][1]['content'])
        self.assertEqual(self.db.query(TaskMessage).filter_by(task_id=self.task.id).count(), 1)


class ModelCompletionTests(unittest.TestCase):
    def test_truncation_and_invalid_envelope_are_rejected(self):
        response = MagicMock()
        client = MagicMock()
        client.__enter__.return_value.post.return_value = response
        model = {'model_name': 'mock', 'api_key': 'test'}
        with patch('app.services.chat_runtime.model_request_options', return_value=('https://example.com', 10, 1000)), \
             patch('app.services.chat_runtime.httpx.Client', return_value=client), \
             patch('app.services.chat_runtime.record_usage'):
            response.json.return_value = {'choices': [{'finish_reason': 'length', 'message': {'content': '{'}}]}
            with self.assertRaisesRegex(ChatProviderError, '未正常结束'):
                request_model(model, [], 0, require_complete=True)
            response.json.return_value = {'choices': 'bad'}
            with self.assertRaisesRegex(ChatProviderError, '响应结构无效'):
                request_model(model, [], 0, require_complete=True)


if __name__ == '__main__':
    unittest.main()
