import { schema } from './schema.js';

// Keep the laboratory schema identical to SQLite so both deployments can exchange backups.
export const TABLES = Object.keys(schema);
const encoder = new TextEncoder();
export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}
export const fail = (status, message) => { throw new ApiError(status, message); };
export const today = () => new Date(Date.now() + 8 * 3600_000).toISOString().slice(0, 10);
export const now = () => new Date().toISOString().replace('T', ' ').replace('Z', '');
export const clean = value => String(value ?? '').trim();
export const codes = value => [...new Set(clean(Array.isArray(value) ? value.join(',') : value).split(/[,，、;；\s]+/).filter(Boolean))];
export const required = (value, label, max = 128) => {
  const result = clean(value);
  if (!result || result.length > max) fail(422, `${label}不能为空且不能超过 ${max} 个字符`);
  return result;
};
export function boundedInt(value, fallback, max = 500) {
  if (value === undefined || value === null || value === '') return fallback;
  const number = Number(value);
  if (!Number.isSafeInteger(number) || number < 1 || number > max) fail(422, `数值应为 1–${max} 的整数`);
  return number;
}

export function decodeRow(table, source) {
  const row = { ...source };
  for (const [key, column] of Object.entries(schema[table])) {
    if (column.type === 'Boolean' && row[key] != null) row[key] = Boolean(row[key]);
    if (column.type === 'JSON' && typeof row[key] === 'string') row[key] = JSON.parse(row[key]);
  }
  return row;
}

export async function all(db, sql, params = []) {
  return (await db.prepare(sql).bind(...params).all()).results;
}

export class Store {
  constructor(rows = {}, revision = 0, { readOnly = false } = {}) {
    this.readOnly = readOnly;
    this.revision = revision;
    this.rows = Object.fromEntries(TABLES.map(table => [table, (rows[table] || []).map(row => decodeRow(table, row))]));
    this.original = readOnly ? null : structuredClone(this.rows);
    if (readOnly) {
      this.cagesById = new Map(this.rows.cages.map(row => [row.id, row]));
      this.genotypesByMouse = new Map();
      for (const row of this.rows.genotype_records) {
        if (!this.genotypesByMouse.has(row.mouse_id)) this.genotypesByMouse.set(row.mouse_id, []);
        this.genotypesByMouse.get(row.mouse_id).push(row);
      }
    }
  }
  static async load(db, tables = TABLES) {
    const queries = ['SELECT value FROM _revision WHERE id=1', ...tables.map(table => `SELECT * FROM "${table}"`)];
    const result = await db.batch(queries.map(sql => db.prepare(sql)));
    return new Store(Object.fromEntries(tables.map((table, i) => [table, result[i + 1].results])), result[0].results[0].value);
  }
  list(table) { return this.rows[table]; }
  find(table, predicate) { return this.rows[table].find(predicate); }
  get(table, id) {
    const row = this.find(table, row => row.id === Number(id));
    if (!row) fail(404, '记录未找到');
    return row;
  }
  add(table, data) {
    const stamp = now();
    const row = Object.fromEntries(Object.entries(schema[table]).map(([key, column]) => [key, column.default === '$now' ? stamp : column.default]));
    row.id = Math.max(0, ...this.rows[table].map(row => row.id)) + 1;
    Object.assign(row, this.fields(table, data));
    this.rows[table].push(row);
    return row;
  }
  fields(table, data) {
    return Object.fromEntries(Object.entries(data).filter(([key, value]) => key !== 'id' && key !== 'created_at' && key !== 'updated_at' && key in schema[table] && value !== undefined));
  }
  update(table, row, data) {
    Object.assign(row, this.fields(table, data));
    if ('updated_at' in row) row.updated_at = now();
    return row;
  }
  remove(table, row) { this.rows[table] = this.rows[table].filter(item => item.id !== row.id); }

  async commit(db) {
    if (this.readOnly) throw new Error('Cannot commit a read-only Store');
    const upserts = [], deletes = [];
    for (const table of TABLES) {
      const before = new Map(this.original[table].map(row => [row.id, row]));
      const after = new Map(this.rows[table].map(row => [row.id, row]));
      const changed = this.rows[table].filter(row => JSON.stringify(row) !== JSON.stringify(before.get(row.id)));
      const removed = this.original[table].filter(row => !after.has(row.id)).map(row => row.id);
      const columns = Object.keys(schema[table]);
      // Existing rows update only changed columns, avoiding writes to unrelated indexes.
      const groups = new Map();
      for (const row of changed) {
        const old = before.get(row.id);
        const fields = old ? columns.filter(key => key !== 'id' && JSON.stringify(row[key]) !== JSON.stringify(old[key])) : columns;
        const key = old ? fields.join(',') : '$insert';
        if (!groups.has(key)) groups.set(key, { fields, insert: !old, rows: [] });
        groups.get(key).rows.push(Object.fromEntries(['id', ...fields].map(key => [key, row[key]])));
      }
      for (const group of groups.values()) for (let offset = 0; offset < group.rows.length; offset += 1000) {
        const payload = JSON.stringify(group.rows.slice(offset, offset + 1000));
        if (encoder.encode(payload).length > 1_800_000) fail(413, '单批数据过大，请减少记录数量');
        if (group.insert) {
          const extract = columns.map(key => `json_extract(value, '$.${key}')`).join(',');
          upserts.push(db.prepare(`INSERT INTO "${table}" (${columns.map(key => `"${key}"`).join(',')}) SELECT ${extract} FROM json_each(?)`).bind(payload));
        } else {
          const updates = group.fields.map(key => `"${key}"=json_extract(patch.value, '$.${key}')`).join(',');
          upserts.push(db.prepare(`UPDATE "${table}" SET ${updates} FROM json_each(?) AS patch WHERE "${table}".id=json_extract(patch.value, '$.id')`).bind(payload));
        }
      }
      if (removed.length) deletes.unshift(db.prepare(`DELETE FROM "${table}" WHERE id IN (SELECT value FROM json_each(?))`).bind(JSON.stringify(removed)));
    }
    if (!upserts.length && !deletes.length) return;
    // A concurrent writer changes _revision through database triggers. The CHECK failure
    // then rolls back the WHOLE D1 batch, including every mouse, assignment and log.
    const guard = db.prepare('INSERT INTO _write_guard(id) SELECT CASE WHEN value=? THEN 1 ELSE 0 END FROM _revision WHERE id=1').bind(this.revision);
    try {
      await db.batch([guard, ...upserts, ...deletes, db.prepare('DELETE FROM _write_guard WHERE id=1')]);
    } catch (error) {
      const message = String(error.message);
      if (/CHECK constraint|_write_guard/i.test(message)) fail(409, '数据刚被其他操作修改，请刷新后重试；此次修改未保存');
      if (/UNIQUE constraint/i.test(message)) fail(409, '存在重复的编号、名称或分配关系，此次修改未保存');
      if (/FOREIGN KEY constraint/i.test(message)) fail(409, '关联记录已变更，请刷新后重试；此次修改未保存');
      throw error;
    }
  }
}
