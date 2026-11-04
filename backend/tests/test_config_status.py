import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import ConfigItem
from app.routers.core import update_config_status
from app.schemas import ConfigStatusIn


class ConfigStatusTests(unittest.TestCase):
    def test_model_switch_preserves_key_and_other_settings(self):
        engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        try:
            model = ConfigItem(category='models', name='Configured model', model_name='model-1',
                               base_url='https://example.com/v1', api_key='real-secret',
                               status='已启用', extra={'max_tokens': 4096})
            db.add(model)
            db.commit()

            result = update_config_status(model.id, ConfigStatusIn(status='已停用'), db)
            db.refresh(model)
            self.assertEqual(result['status'], '已停用')
            self.assertEqual(result['api_key'], '已配置')
            self.assertEqual(model.api_key, 'real-secret')
            self.assertEqual(model.model_name, 'model-1')
            self.assertEqual(model.extra, {'max_tokens': 4096})

            update_config_status(model.id, ConfigStatusIn(status='已启用'), db)
            db.refresh(model)
            self.assertEqual(model.status, '已启用')
        finally:
            db.close()
            engine.dispose()


if __name__ == '__main__':
    unittest.main()
