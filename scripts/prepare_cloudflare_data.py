"""Prepare a read-only SQLite snapshot for the FIRST import into an empty D1 database.

The source database is never updated. Credentials are written only to ignored local
files, never to SQL committed to Git or to terminal output.
"""
import argparse
import base64
import hashlib
import json
import re
import secrets
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def password_hash(password):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    encode = lambda value: base64.b64encode(value).decode().replace('+', '.').rstrip('=')
    return f'$pbkdf2-sha256$100000${encode(salt)}${encode(digest)}'


def verifies(password, encoded):
    try:
        _, scheme, rounds, salt, expected = encoded.split('$')
        if scheme != 'pbkdf2-sha256':
            return False
        decode = lambda value: base64.b64decode(value.replace('.', '+') + '=' * (-len(value) % 4))
        return secrets.compare_digest(hashlib.pbkdf2_hmac('sha256', password.encode(), decode(salt), int(rounds)), decode(expected))
    except (TypeError, ValueError):
        return False


def sql_literal(value):
    if value is None:
        return 'NULL'
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, bytes):
        return "X'" + value.hex() + "'"
    # NUL cannot appear literally in a Wrangler SQL input file.
    text = str(value)
    if '\x00' in text:
        return 'CAST(' + "X'" + text.encode().hex() + "' AS TEXT)"
    return "'" + text.replace("'", "''") + "'"


def prepare(source_path, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = output_dir / 'sqlite-snapshot.db'
    if snapshot_path.exists():
        raise ValueError(f'输出快照已存在，为避免覆盖，请指定新的 --output 目录：{snapshot_path}')
    text = (ROOT / 'cloudflare/schema.js').read_text(encoding='utf-8')
    schema = json.loads(re.search(r'export const schema = (.*?);\nexport const createSql', text, re.S).group(1))
    tables = list(schema)
    source = sqlite3.connect(source_path.resolve().as_uri() + '?mode=ro', uri=True)
    snapshot = sqlite3.connect(snapshot_path)
    try:
        if source.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('源数据库完整性检查失败')
        if source.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('源数据库存在外键错误')
        source.backup(snapshot)
    finally:
        source.close()
    accounts = []
    for username, old_password in [('admin', 'admin123')]:
        row = snapshot.execute('SELECT id,hashed_password FROM users WHERE lower(username)=lower(?)', (username,)).fetchone()
        if row and verifies(old_password, row[1]):
            password = secrets.token_urlsafe(18)
            snapshot.execute('UPDATE users SET hashed_password=? WHERE id=?', (password_hash(password), row[0]))
            accounts.append({'username': username, 'password': password})
    snapshot.commit()
    if not snapshot.execute("SELECT 1 FROM users WHERE role='admin' AND is_active=1 LIMIT 1").fetchone():
        raise ValueError('源数据库没有启用的管理员账号')
    counts, table_hashes = {}, {}
    sql_path = output_dir / 'initial-data.sql'
    with sql_path.open('w', encoding='utf-8', newline='\n') as output:
        output.write('-- Private initial data. Import only into a NEW, EMPTY D1 database.\n')
        # A guard fails before inserting anything if a target already contains laboratory data.
        nonempty = ' + '.join(f'(SELECT COUNT(*) FROM "{table}")' for table in tables)
        output.write(f'INSERT INTO _write_guard(id) VALUES(CASE WHEN ({nonempty})=0 THEN 1 ELSE 0 END);\n')
        for table, metadata in schema.items():
            columns = list(metadata)
            names = ','.join('"' + name + '"' for name in columns)
            rows = snapshot.execute(f'SELECT {names} FROM "{table}" ORDER BY id').fetchall()
            counts[table] = len(rows)
            table_hashes[table] = hashlib.sha256(json.dumps(rows, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
            for row in rows:
                output.write(f'INSERT INTO "{table}" ({names}) VALUES (' + ','.join(map(sql_literal, row)) + ');\n')
        output.write('DELETE FROM _write_guard WHERE id=1;\n')
    snapshot.close()
    manifest = {'source': str(source_path.resolve()), 'snapshot': str(snapshot_path.resolve()), 'counts': counts, 'table_sha256': table_hashes, 'rotated_default_accounts': [row['username'] for row in accounts]}
    (output_dir / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    secret_path = ROOT / '.dev.vars'
    if not secret_path.exists():
        secret_path.write_text('SECRET_KEY="' + secrets.token_urlsafe(48) + '"\n', encoding='utf-8')
    credentials = 'Cloudflare 测试/初次部署账号（仅迁移副本中的默认密码已更换；本地原数据库未修改）\n\n'
    credentials += '\n'.join(f"账号：{row['username']}\n密码：{row['password']}\n" for row in accounts)
    if not accounts:
        credentials += '没有发现使用已知默认密码的账号；使用原数据库中的账号密码登录。\n'
    (output_dir / 'credentials.txt').write_text(credentials, encoding='utf-8')
    print(json.dumps({'counts': counts, 'rotated_default_accounts': manifest['rotated_default_accounts'], 'output': str(output_dir.resolve())}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / 'data/mouse-manager.db')
    parser.add_argument('--output', type=Path, default=ROOT / 'migration-output/initial')
    args = parser.parse_args()
    prepare(args.source, args.output)
