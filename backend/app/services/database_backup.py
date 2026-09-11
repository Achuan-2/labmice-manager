"""Consistent SQLite snapshots and validated, transactional restoration."""
import asyncio
import sqlite3
from contextlib import closing
from pathlib import Path


class DatabaseMaintenanceMiddleware:
    """Drain API requests before restore; keep ordinary requests concurrent.

    The application runs with one worker, as in the supplied launch scripts.
    """
    def __init__(self, app):
        self.app = app
        self.condition = asyncio.Condition()
        self.active = 0
        self.restoring = False

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or not scope['path'].startswith('/api/'):
            return await self.app(scope, receive, send)
        exclusive = scope['path'] == '/api/import-export/database/restore' and scope['method'] == 'POST'
        async with self.condition:
            await self.condition.wait_for(lambda: not self.restoring)
            if exclusive:
                self.restoring = True
                try:
                    await self.condition.wait_for(lambda: self.active == 0)
                except BaseException:
                    self.restoring = False
                    self.condition.notify_all()
                    raise
            else:
                self.active += 1
        try:
            await self.app(scope, receive, send)
        finally:
            async with self.condition:
                if exclusive:
                    self.restoring = False
                else:
                    self.active -= 1
                self.condition.notify_all()


def snapshot(source, target):
    # SQLite backup includes committed WAL pages, unlike copying the .db file.
    with closing(sqlite3.connect(Path(source).resolve().as_uri() + '?mode=ro', uri=True)) as src:
        with closing(sqlite3.connect(str(target))) as dst:
            src.backup(dst)


def validate_database(path, tables):
    try:
        with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)) as db:
            if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise ValueError('数据库完整性检查失败')
            existing_tables = {
                row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            for table in tables:
                if table.name not in existing_tables:
                    raise ValueError(f'数据库缺少数据表：{table.name}，请使用当前版本导出的备份')
                columns = {row[1] for row in db.execute(f'PRAGMA table_info("{table.name}")')}
                if not {column.name for column in table.columns}.issubset(columns):
                    raise ValueError(f'数据表 {table.name} 版本不兼容，请使用当前版本导出的备份')
            if db.execute('PRAGMA foreign_key_check').fetchone():
                raise ValueError('数据库存在无效的数据关联，无法恢复')
    except sqlite3.DatabaseError as exc:
        raise ValueError('文件不是有效的 SQLite 数据库，或数据库已损坏') from exc


def restore_database(source, target, safety_backup, tables, engine):
    validate_database(source, tables)
    engine.dispose()
    snapshot(target, safety_backup)
    # Backup writes the destination in a SQLite transaction, preserving its
    # identity and avoiding unsafe replacement of an open WAL database file.
    snapshot(source, target)
    engine.dispose()
