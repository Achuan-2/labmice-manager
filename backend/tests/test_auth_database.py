import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from backend.app.auth_database import initialize_auth_database
from backend.app.auth import init_default_admin
from backend.app.models.models import SystemSetting, User


class AuthDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.business_engine = create_engine(f'sqlite:///{root / "business.db"}')
        self.auth_engine = create_engine(f'sqlite:///{root / "accounts.db"}')

    def tearDown(self):
        self.business_engine.dispose()
        self.auth_engine.dispose()
        self.temp.cleanup()

    def test_migrates_legacy_users_and_removes_business_user_table(self):
        User.__table__.create(self.business_engine)
        with Session(self.business_engine) as db:
            db.add(User(
                username='legacy-admin',
                hashed_password='stored-hash',
                role='admin',
                display_name='旧管理员',
                is_active=True,
            ))
            db.commit()

        migrated = initialize_auth_database(
            User.__table__,
            (SystemSetting.__table__,),
            source_engine=self.business_engine,
            target_engine=self.auth_engine,
        )

        self.assertEqual(migrated, 1)
        self.assertNotIn('users', inspect(self.business_engine).get_table_names())
        with Session(self.auth_engine) as db:
            user = db.query(User).one()
            self.assertEqual(user.username, 'legacy-admin')
            self.assertEqual(user.hashed_password, 'stored-hash')

    def test_creates_empty_account_database_for_fresh_install(self):
        migrated = initialize_auth_database(
            User.__table__,
            (SystemSetting.__table__,),
            source_engine=self.business_engine,
            target_engine=self.auth_engine,
        )

        self.assertEqual(migrated, 0)
        self.assertIn('users', inspect(self.auth_engine).get_table_names())
        self.assertIn('system_settings', inspect(self.auth_engine).get_table_names())
        self.assertNotIn('users', inspect(self.business_engine).get_table_names())

        with Session(self.auth_engine) as db:
            init_default_admin(db)
            self.assertEqual([user.username for user in db.query(User).all()], ['admin'])


if __name__ == '__main__':
    unittest.main()
