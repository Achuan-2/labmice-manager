// The asm build is self-contained and avoids browser `location.href` lookup,
// which is unavailable in Cloudflare Workers. It is used only for backup
// validation/export; live queries continue to use D1.
import initSqlJs from 'sql.js/dist/sql-asm.js';
import { schema, createSql } from './schema.js';
import { Store, TABLES, all, fail, now, decodeRow } from './database.js';

let sqlitePromise;
export function configureSqlite() {}
async function sqlite() {
  if (!sqlitePromise) sqlitePromise = initSqlJs();
  return sqlitePromise;
}
const encodeValue = value => value === undefined || value === null ? null : typeof value === 'boolean' ? Number(value) : typeof value === 'object' ? JSON.stringify(value) : value;
const download = (bytes, filename) => new Response(bytes, { headers: { 'Content-Type': 'application/octet-stream', 'Content-Disposition': `attachment; filename="${filename}"`, 'Cache-Control': 'no-store' } });

export async function databaseBytes(rows) {
  const SQL = await sqlite(), target = new SQL.Database();
  try {
    target.run(createSql);
    target.run('PRAGMA foreign_keys=ON; BEGIN; PRAGMA defer_foreign_keys=ON;');
    for (const table of TABLES) {
      const columns = Object.keys(schema[table]);
      const insert = target.prepare(`INSERT INTO "${table}" (${columns.map(key => `"${key}"`).join(',')}) VALUES (${columns.map(() => '?').join(',')})`);
      try { for (const row of rows[table] || []) insert.run(columns.map(key => encodeValue(row[key]))); }
      finally { insert.free(); }
    }
    target.run('COMMIT;');
    const issues = target.exec('PRAGMA foreign_key_check;');
    if (issues.length) fail(409, '数据关联检查未通过，无法生成备份');
    return target.export();
  } finally { target.close(); }
}
export async function readDatabase(bytes) {
  if (bytes.byteLength > 20 * 1024 * 1024) fail(413, '云端数据库导入最大支持 20 MB');
  if (new TextDecoder().decode(new Uint8Array(bytes).slice(0, 16)) !== 'SQLite format 3\0') fail(400, '不是有效的 SQLite 数据库文件');
  const SQL = await sqlite();
  let source;
  try { source = new SQL.Database(new Uint8Array(bytes)); }
  catch { fail(400, '数据库文件损坏或格式不受支持'); }
  try {
    source.run('PRAGMA query_only=ON;');
    const integrity = source.exec('PRAGMA integrity_check;');
    if (integrity[0]?.values[0]?.[0] !== 'ok') fail(400, '数据库完整性检查未通过');
    const existing = new Map(source.exec("SELECT name,type FROM sqlite_master WHERE type IN ('table','view')")[0]?.values || []);
    const rows = {};
    for (const table of TABLES) {
      if (existing.get(table) !== 'table') fail(400, `数据库缺少数据表 ${table}，请先用当前版本导出完整备份`);
      const actualColumns = new Set(source.exec(`PRAGMA table_info("${table}")`)[0].values.map(row => row[1]));
      const columns = Object.keys(schema[table]);
      if (columns.some(column => !actualColumns.has(column))) fail(400, `数据表 ${table} 的结构与当前版本不兼容`);
      const result = source.exec(`SELECT ${columns.map(column => `"${column}"`).join(',')} FROM "${table}" LIMIT 50001`)[0];
      if (result?.values.length > 50000) fail(413, '单表记录过多，请使用命令行迁移工具');
      rows[table] = (result?.values || []).map(values => decodeRow(table, Object.fromEntries(columns.map((column, index) => [column, values[index]]))));
    }
    if (!rows.users.some(user => user.role === 'admin' && user.is_active && user.hashed_password)) fail(400, '备份中必须包含可用的管理员账号');
    // Validate only the supported schema, including foreign keys. Never execute SQL from uploads.
    await databaseBytes(rows);
    return rows;
  } finally { source.close(); }
}

export async function exportDatabase(db) {
  const store = await Store.load(db);
  return download(await databaseBytes(store.rows), `mouse-manager_${Date.now()}.db`);
}

export async function restoreDatabase(db, form) {
  const file = form.get('file');
  if (!file || typeof file.arrayBuffer !== 'function' || !file.name?.toLowerCase().endsWith('.db')) fail(400, '请选择 .db 数据库备份文件');
  // Parse and validate before acquiring the current revision; no side effects on rejection.
  const incoming = await readDatabase(await file.arrayBuffer());
  let euthanasiaOwner = incoming.claimers.find(row => row.name === '安乐死');
  if (!euthanasiaOwner) {
    euthanasiaOwner = { id: Math.max(0, ...incoming.claimers.map(row => row.id)) + 1, name: '安乐死', role: '其他', color: '#6b7280', notes: '系统默认领取人；选择后小鼠状态自动变为死亡', created_at: now() };
    incoming.claimers.push(euthanasiaOwner);
  }
  for (const mouse of incoming.mice) if (mouse.owner_name === '安乐死' || mouse.owner_id === euthanasiaOwner.id) {
    mouse.owner_id = euthanasiaOwner.id; mouse.owner_name = euthanasiaOwner.name; mouse.status = '死亡'; mouse.cage_id = null;
  }
  const current = await Store.load(db);
  const backupId = crypto.randomUUID(), stamp = now();
  const statements = [db.prepare('INSERT INTO _write_guard(id) SELECT CASE WHEN value=? THEN 1 ELSE 0 END FROM _revision WHERE id=1').bind(current.revision)];
  // A durable safety copy is saved in the SAME transaction as the restore.
  const backupChunks = [];
  for (const table of TABLES) {
    const rows = current.rows[table];
    for (let offset = 0; offset < Math.max(1, rows.length); offset += 1000) backupChunks.push({ table_name: table, chunk_no: offset / 1000, rows_json: rows.slice(offset, offset + 1000) });
  }
  // Group backup chunks into bounded parameters, keeping a normal restore within
  // the Free plan's 50 SQL queries per invocation without splitting its transaction.
  let pending = [], pendingSize = 2;
  const flushBackup = () => {
    if (!pending.length) return;
    statements.push(db.prepare("INSERT INTO _backups(backup_id,created_at,table_name,chunk_no,rows_json) SELECT ?,?,json_extract(value,'$.table_name'),json_extract(value,'$.chunk_no'),json_extract(value,'$.rows_json') FROM json_each(?)").bind(backupId, stamp, JSON.stringify(pending)));
    pending = []; pendingSize = 2;
  };
  for (const chunk of backupChunks) {
    const size = new TextEncoder().encode(JSON.stringify(chunk)).length + 1;
    if (size > 1_800_000) fail(413, '数据块过大，请使用命令行迁移');
    if (pendingSize + size > 1_800_000) flushBackup();
    pending.push(chunk); pendingSize += size;
  }
  flushBackup();
  for (const table of [...TABLES].reverse()) statements.push(db.prepare(`DELETE FROM "${table}"`));
  for (const table of TABLES) {
    const columns = Object.keys(schema[table]);
    for (let offset = 0; offset < incoming[table].length; offset += 1000) {
      const sql = `INSERT INTO "${table}" (${columns.map(key => `"${key}"`).join(',')}) SELECT ${columns.map(key => `json_extract(value,'$.${key}')`).join(',')} FROM json_each(?)`;
      statements.push(db.prepare(sql).bind(JSON.stringify(incoming[table].slice(offset, offset + 1000))));
    }
  }
  statements.push(db.prepare('DELETE FROM _write_guard WHERE id=1'));
  try { await db.batch(statements); }
  catch (error) {
    if (/CHECK constraint|_write_guard/i.test(error.message)) fail(409, '数据刚被其他操作修改，本次恢复已取消，请重试');
    throw error;
  }
  return { message: '数据库已完整恢复，请使用备份中的账号重新登录', safety_backup: backupId, safety_backup_url: `/api/import-export/database/backups/${backupId}`, deployment: 'cloudflare' };
}
export async function backupList(db) {
  return all(db, 'SELECT backup_id,MIN(created_at) AS created_at FROM _backups GROUP BY backup_id ORDER BY created_at DESC');
}
export async function downloadBackup(db, id) {
  const chunks = await all(db, 'SELECT table_name,rows_json FROM _backups WHERE backup_id=? ORDER BY table_name,chunk_no', [id]);
  if (!chunks.length) fail(404, '备份未找到');
  const rows = Object.fromEntries(TABLES.map(table => [table, []]));
  for (const chunk of chunks) rows[chunk.table_name].push(...JSON.parse(chunk.rows_json));
  return download(await databaseBytes(rows), `mouse-manager_before_restore_${id}.db`);
}
