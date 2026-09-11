"""Dedicated SQLite storage for user accounts and password hashes."""
import os

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import sessionmaker

from backend.app.database import DATA_DIR, engine as business_engine


AUTH_DB_PATH = os.path.join(DATA_DIR, 'accounts.db')
AUTH_DATABASE_URL = f'sqlite:///{AUTH_DB_PATH}'

auth_engine = create_engine(
    AUTH_DATABASE_URL,
    connect_args={'check_same_thread': False},
)
AuthSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=auth_engine)


@event.listens_for(auth_engine, 'connect')
def set_auth_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute('PRAGMA journal_mode=WAL')
    cursor.execute('PRAGMA synchronous=NORMAL')
    cursor.close()


def get_auth_db():
    db = AuthSessionLocal()
    try:
        yield db
    finally:
        db.close()


def initialize_auth_database(user_table, extra_tables=(), source_engine=business_engine, target_engine=auth_engine):
    """Create accounts.db and migrate users from the former combined database.

    Account IDs are local to the authentication database and are not referenced
    by business tables, so username is the stable key during a merge.
    """
    user_table.create(bind=target_engine, checkfirst=True)
    for table in extra_tables:
        table.create(bind=target_engine, checkfirst=True)
    if 'users' not in inspect(source_engine).get_table_names():
        return 0

    with source_engine.connect() as source:
        legacy_users = source.exec_driver_sql(
            'SELECT username, hashed_password, role, display_name, is_active, created_at '
            'FROM users'
        ).mappings().all()

    with target_engine.begin() as target:
        existing = {
            row[0] for row in target.exec_driver_sql('SELECT username FROM users').fetchall()
        }
        migrated = 0
        for user in legacy_users:
            if user['username'] in existing:
                continue
            target.exec_driver_sql(
                'INSERT INTO users '
                '(username, hashed_password, role, display_name, is_active, created_at) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                (
                    user['username'],
                    user['hashed_password'],
                    user['role'],
                    user['display_name'],
                    user['is_active'],
                    user['created_at'],
                ),
            )
            existing.add(user['username'])
            migrated += 1

        missing = {
            user['username'] for user in legacy_users
            if user['username'] not in existing
        }
        if missing:
            raise RuntimeError(f'账号数据库迁移不完整：{sorted(missing)}')

    # The account copy is durable before the old table is removed.
    with source_engine.begin() as source:
        source.exec_driver_sql('DROP TABLE users')
    return migrated
