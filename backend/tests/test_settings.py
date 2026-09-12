import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.auth import create_access_token, get_password_hash
from backend.app.auth_database import get_auth_db
from backend.app.models.models import SystemSetting, User
from backend.app.routers import settings


class SettingsApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine(
            f'sqlite:///{Path(self.temp.name) / "accounts.db"}',
            connect_args={'check_same_thread': False},
        )
        User.__table__.create(self.engine)
        SystemSetting.__table__.create(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with Session(self.engine) as db:
            db.add(User(
                username='admin',
                hashed_password=get_password_hash('test-password'),
                role='admin',
                display_name='管理员',
                is_active=True,
            ))
            db.commit()

        app = FastAPI()
        app.include_router(settings.router)

        def test_db():
            db = self.sessions()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_auth_db] = test_db
        self.client = TestClient(app)
        token = create_access_token({'sub': 'admin', 'role': 'admin'})
        self.admin_headers = {'Authorization': f'Bearer {token}'}

    def tearDown(self):
        self.engine.dispose()
        self.temp.cleanup()

    def test_default_name_and_admin_update(self):
        response = self.client.get('/api/settings/public')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'system_name': '课题组小鼠管理系统',
            'transfer_rooms': ['东五', '东四'],
        })

        self.assertEqual(
            self.client.put('/api/settings', json={'system_name': '其他实验室'}).status_code,
            401,
        )
        updated = self.client.put(
            '/api/settings',
            json={'system_name': '  动物资源平台  '},
            headers=self.admin_headers,
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()['system_name'], '动物资源平台')
        self.assertEqual(
            self.client.get('/api/settings/public').json()['system_name'],
            '动物资源平台',
        )

    def test_rejects_blank_system_name(self):
        response = self.client.put(
            '/api/settings',
            json={'system_name': '   '},
            headers=self.admin_headers,
        )
        self.assertEqual(response.status_code, 422)

    def test_uses_legacy_group_name_when_system_name_is_not_set(self):
        with Session(self.engine) as db:
            db.add(SystemSetting(key='group_name', value='神经环路课题组'))
            db.commit()

        response = self.client.get('/api/settings/public')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['system_name'], '神经环路课题组小鼠管理系统')

    def test_transfer_room_options_can_be_added_renamed_and_deleted(self):
        added = self.client.post(
            '/api/settings/transfer-rooms',
            json={'name': ' 枫林 '},
            headers=self.admin_headers,
        )
        self.assertEqual(added.status_code, 200)
        self.assertEqual(added.json()['transfer_rooms'], ['东五', '东四', '枫林'])

        renamed = self.client.put(
            '/api/settings/transfer-rooms/%E6%9E%AB%E6%9E%97',
            json={'name': '枫林实验楼'},
            headers=self.admin_headers,
        )
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed.json()['transfer_rooms'], ['东五', '东四', '枫林实验楼'])

        deleted = self.client.delete(
            '/api/settings/transfer-rooms/%E4%B8%9C%E5%9B%9B',
            headers=self.admin_headers,
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.json()['transfer_rooms'], ['东五', '枫林实验楼'])
        self.assertEqual(
            self.client.get('/api/settings/public').json()['transfer_rooms'],
            ['东五', '枫林实验楼'],
        )


if __name__ == '__main__':
    unittest.main()
