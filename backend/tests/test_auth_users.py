import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.auth import create_access_token, get_password_hash
from backend.app.auth_database import get_auth_db
from backend.app.models.models import User
from backend.app.routers import auth


class AuthUserApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine(
            f'sqlite:///{Path(self.temp.name) / "accounts.db"}',
            connect_args={'check_same_thread': False},
        )
        User.__table__.create(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        with Session(self.engine) as db:
            admin = User(
                username='admin',
                hashed_password=get_password_hash('test-password'),
                role='admin',
                display_name='管理员',
                is_active=True,
            )
            user = User(
                username='guest',
                hashed_password=get_password_hash('test-password'),
                role='guest',
                display_name='原名称',
                is_active=True,
            )
            db.add_all([admin, user])
            db.commit()
            self.user_id = user.id

        app = FastAPI()
        app.include_router(auth.router)

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

    def test_admin_can_update_user_display_name(self):
        response = self.client.put(
            f'/api/auth/admins/{self.user_id}/display-name',
            json={'display_name': '  新用户名称  '},
            headers=self.admin_headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['display_name'], '新用户名称')
        with Session(self.engine) as db:
            self.assertEqual(db.get(User, self.user_id).display_name, '新用户名称')

    def test_display_name_update_requires_admin(self):
        response = self.client.put(
            f'/api/auth/admins/{self.user_id}/display-name',
            json={'display_name': '新用户名称'},
        )
        self.assertEqual(response.status_code, 401)

    def test_rejects_blank_display_name(self):
        response = self.client.put(
            f'/api/auth/admins/{self.user_id}/display-name',
            json={'display_name': '   '},
            headers=self.admin_headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['detail'], '用户名称不能为空')


if __name__ == '__main__':
    unittest.main()
