import { all, Store, boundedInt, fail, codes, decodeRow, today } from './database.js';
import { enrichMouse, mouseByCode, normalizeStrain } from './domain.js';
import { schema } from './schema.js';

function filterSQL(query, fields, keywordFields = []) {
  const clauses = [], values = [];
  for (const [parameter, definition] of Object.entries(fields)) {
    if (!query[parameter]) continue;
    const [column, mode] = Array.isArray(definition) ? definition : [definition, '='];
    clauses.push(`${column} ${mode === 'like' ? 'LIKE' : '='} ?`);
    values.push(mode === 'like' ? `%${query[parameter].trim()}%` : query[parameter].trim());
  }
  if (query.keyword && keywordFields.length) {
    clauses.push(`(${keywordFields.map(column => `${column} LIKE ?`).join(' OR ')})`);
    for (const field of keywordFields) values.push(`%${query.keyword.trim()}%`);
  }
  return { clauses, values };
}
function where(clauses) { return clauses.length ? ' WHERE ' + clauses.join(' AND ') : ''; }
function booleanQuery(value) {
  if (value === undefined) return undefined;
  if (['true', '1'].includes(value)) return true;
  if (['false', '0'].includes(value)) return false;
  fail(422, '布尔参数必须为 true 或 false');
}
const parentTokens = value => [...new Set(String(value || '').split(/[+、/,，\s\\]+/).map(token => token.trim()).filter(token => /^[A-Za-z0-9_-]{1,32}$/.test(token) && /\d/.test(token)))];
const normalizedParentsSQL = `(',' || lower(replace(replace(replace(replace(replace(replace(replace(replace(replace(coalesce(m.parents,''),'+',','),'、',','),'/',','),'，',','),' ',','),'\\',','),char(9),','),char(10),','),char(13),',')) || ',')`;

export async function listMice(db, query) {
  const { clauses, values } = filterSQL(query, { mouse_code: 'm.mouse_code', cage_code: 'c.cage_code', strain: 'm.strain', gender: 'm.gender', owner_name: 'm.owner_name', status: 'm.status' }, ['m.mouse_code', 'm.strain', 'm.parents', 'm.notes', 'm.owner_name', 'm.genotype_1', 'c.cage_code']);
  if (query.room) { clauses.push('(c.room=? OR m.source_room=?)'); values.push(query.room, query.room); }
  const parents = parentTokens(query.parents);
  if (parents.length) {
    clauses.push(`(${parents.map(() => `${normalizedParentsSQL} LIKE ?`).join(' OR ')})`);
    values.push(...parents.map(parent => `%,${parent.toLowerCase()},%`));
  }
  const inCage = booleanQuery(query.in_cage), hasOwner = booleanQuery(query.has_owner);
  if (inCage === true) clauses.push("m.cage_id IS NOT NULL AND m.status!='出笼'");
  if (inCage === false) clauses.push('m.cage_id IS NULL');
  if (hasOwner !== undefined) clauses.push(`m.owner_id IS ${hasOwner ? 'NOT ' : ''}NULL`);
  const page = boundedInt(query.page, 1, 100000), page_size = boundedInt(query.page_size, 50);
  const base = ' FROM mice m LEFT JOIN cages c ON c.id=m.cage_id' + where(clauses);
  const keywordOrder = query.keyword ? 'CASE WHEN m.mouse_code LIKE ? THEN 0 WHEN m.mouse_code LIKE ? THEN 1 WHEN m.mouse_code LIKE ? THEN 2 WHEN m.parents LIKE ? THEN 4 ELSE 3 END, ' : '';
  const order = ` ORDER BY ${keywordOrder}CASE WHEN m.status='在笼' THEN 0 WHEN m.status IN ('出笼','死亡') THEN 2 ELSE 1 END, m.id DESC LIMIT ? OFFSET ?`;
  const params = [...values, ...(query.keyword ? [query.keyword.trim(), `${query.keyword.trim()}%`, `%${query.keyword.trim()}%`, `%${query.keyword.trim()}%`] : []), page_size, (page - 1) * page_size];
  const countBase = clauses.some(clause => /\bc\./.test(clause)) ? base : ' FROM mice m' + where(clauses);
  const genotypeFields = Object.keys(schema.genotype_records).map(key => `'${key}',g."${key}"`).join(',');
  const results = await db.batch([
    db.prepare('SELECT COUNT(*) AS total' + countBase).bind(...values),
    // Materialize the page once, then use the mouse_id index for its genotype rows.
    db.prepare(`WITH page AS MATERIALIZED (SELECT m.*,c.cage_code,c.room AS joined_room${base}${order})
      SELECT page.*,(SELECT json_group_array(json_object(${genotypeFields})) FROM genotype_records g WHERE g.mouse_id=page.id) AS linked_genotypes FROM page`).bind(...params),
  ]);
  const genotypes = results[1].results.flatMap(row => JSON.parse(row.linked_genotypes || '[]'));
  const rows = results[1].results.map(({ linked_genotypes, ...row }) => row);
  const cages = [...new Map(rows.filter(row => row.cage_id).map(row => [row.cage_id, { id: row.cage_id, cage_code: row.cage_code, room: row.joined_room }])).values()];
  const store = new Store({ mice: rows, cages, genotype_records: genotypes }, 0, { readOnly: true });
  return { total: results[0].results[0].total, page, page_size, items: rows.map(row => { const { joined_room, ...mouse } = enrichMouse(store, row); return mouse; }) };
}

export async function listParents(db) {
  const rows = await all(db, "SELECT DISTINCT parents FROM mice WHERE parents IS NOT NULL AND parents!=''");
  return [...new Set(rows.flatMap(row => parentTokens(row.parents)))].sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
}

export async function getMouse(db, identifier, byCode = false) {
  let row = await db.prepare(`SELECT * FROM mice WHERE ${byCode ? 'mouse_code' : 'id'}=?`).bind(identifier).first();
  if (!row && byCode) row = await db.prepare('SELECT * FROM mice WHERE mouse_code LIKE ? ORDER BY id LIMIT 1').bind(`%${identifier}%`).first();
  if (!row) {
    if (byCode) {
      const genotypes = await all(db, 'SELECT * FROM genotype_records WHERE mouse_code=? ORDER BY id DESC', [identifier]);
      return mouseByCode(new Store({ genotype_records: genotypes }), identifier);
    }
    fail(404, '小鼠未找到');
  }
  const result = await db.batch([
    db.prepare('SELECT * FROM cages WHERE id=?').bind(row.cage_id),
    db.prepare('SELECT * FROM genotype_records WHERE mouse_id=? OR mouse_code=?').bind(row.id, row.mouse_code),
    db.prepare('SELECT * FROM transfer_logs WHERE mouse_codes LIKE ? ORDER BY id DESC').bind(`%${row.mouse_code}%`),
  ]);
  return enrichMouse(new Store({ cages: result[0].results, genotype_records: result[1].results, transfer_logs: result[2].results }), row, true);
}

export async function listCages(db, query, id = null) {
  const { clauses, values } = filterSQL(query, { room: 'c.room', cage_code: ['c.cage_code', 'like'], strain: 'c.strain', gender: 'c.gender' });
  if (id !== null) { clauses.push('c.id=?'); values.push(id); }
  if (booleanQuery(query.only_with_mice)) clauses.push('EXISTS(SELECT 1 FROM mice m WHERE m.cage_id=c.id)');
  const suffix = where(clauses);
  const result = await db.batch([
    db.prepare('SELECT c.* FROM cages c' + suffix + ' ORDER BY c.room,c.cage_code').bind(...values),
    db.prepare('SELECT m.* FROM mice m JOIN cages c ON c.id=m.cage_id' + suffix).bind(...values),
    db.prepare('SELECT g.* FROM genotype_records g JOIN mice m ON m.id=g.mouse_id JOIN cages c ON c.id=m.cage_id' + suffix).bind(...values),
  ]);
  const store = new Store({ cages: result[0].results, mice: result[1].results, genotype_records: result[2].results }, 0, { readOnly: true });
  const mice = new Map();
  for (const mouse of store.list('mice')) {
    if (!mice.has(mouse.cage_id)) mice.set(mouse.cage_id, []);
    mice.get(mouse.cage_id).push(enrichMouse(store, mouse));
  }
  const cages = store.list('cages').map(cage => ({ ...cage, mice: mice.get(cage.id) || [], mouse_count: mice.get(cage.id)?.length || 0 }));
  if (id !== null && !cages.length) fail(404, '笼位未找到');
  return id !== null ? cages[0] : cages;
}

export const roomCategory = name => /实验动物楼|江湾发育所/.test(name) ? '繁育鼠房' : name.includes('东四') ? '临时鼠房' : '实验鼠房';
export async function rooms(db, query) {
  const rows = await all(db, `WITH names AS (SELECT name FROM rooms WHERE name!='' UNION SELECT room FROM cages WHERE room!=''),
    cage_counts AS (SELECT room,COUNT(*) AS n FROM cages GROUP BY room),
    mouse_counts AS (SELECT c.room,COUNT(*) AS n FROM mice m JOIN cages c ON c.id=m.cage_id GROUP BY c.room)
    SELECT names.name,r.category,COALESCE(cc.n,0) AS cage_count,COALESCE(mc.n,0) AS mouse_count FROM names
    LEFT JOIN rooms r ON r.name=names.name LEFT JOIN cage_counts cc ON cc.room=names.name LEFT JOIN mouse_counts mc ON mc.room=names.name ORDER BY names.name`);
  return booleanQuery(query.include_categories) ? rows.map(row => ({ ...row, category: row.category === '使用鼠房' ? '实验鼠房' : row.category || roomCategory(row.name) })) : rows.map(row => row.name);
}

export async function listGenotypes(db, query) {
  const { clauses, values } = filterSQL(query, { mouse_code: ['g.mouse_code', 'like'], strain: 'g.strain', genotype_1: 'g.genotype_1', parents: ['g.parents', 'like'] }, ['g.mouse_code', 'g.strain', 'g.parents', 'g.genotype_1', 'g.genotype_2', 'g.notes']);
  const page = query.page ? boundedInt(query.page, 1, 100000) : null;
  const page_size = boundedInt(query.page_size, 50);
  const limit = page ? page_size : boundedInt(query.limit, 200, 1000);
  const base = ' FROM genotype_records g LEFT JOIN mice m ON m.id=g.mouse_id' + where(clauses);
  const select = `SELECT g.*, COALESCE(NULLIF(g.parents,''),m.parents) AS parents,COALESCE(NULLIF(g.strain,''),m.strain,'') AS strain,
    COALESCE(NULLIF(g.dob,''),m.dob) AS dob,COALESCE(NULLIF(g.gender,''),m.gender) AS gender`;
  const priority = query.keyword ? 'CASE WHEN g.mouse_code LIKE ? THEN 0 WHEN g.mouse_code LIKE ? THEN 1 WHEN g.mouse_code LIKE ? THEN 2 ELSE 3 END, ' : '';
  const order = ` ORDER BY ${priority}CASE WHEN g.test_date IS NULL OR g.test_date='' THEN 1 ELSE 0 END,g.test_date DESC,g.id DESC LIMIT ? OFFSET ?`;
  const result = await db.batch([
    db.prepare('SELECT COUNT(*) AS total FROM genotype_records g' + where(clauses)).bind(...values),
    db.prepare(select + base + order).bind(...values, ...(query.keyword ? [query.keyword.trim(), `${query.keyword.trim()}%`, `%${query.keyword.trim()}%`] : []), limit, page ? (page - 1) * page_size : 0),
  ]);
  const items = result[1].results;
  return page ? { total: result[0].results[0].total, page, page_size, items } : items;
}

export async function members(db) {
  return (await all(db, "SELECT c.*,COUNT(m.id) AS mouse_count FROM claimers c LEFT JOIN mice m ON m.owner_id=c.id GROUP BY c.id ORDER BY CASE WHEN c.name='安乐死' THEN 1 ELSE 0 END,c.name")).map(row => ({ ...row, role: row.role === '实验管家' ? '管家' : row.role || '学生', color: row.color || '#2563eb' }));
}

export async function simpleList(db, table, query) {
  const config = {
    transfer_requests: { filters: { demander: ['demander', 'like'], status: 'status', strain: ['strain', 'like'] }, order: 'id DESC' },
    transfer_logs: { filters: { claimer_name: 'claimer_name', action_type: 'action_type', status: 'status' }, order: 'id DESC' },
    primers: { filters: { strain: 'strain_short' }, keywords: ['strain_short', 'strain_full', 'sequence', 'band_size', 'notes'], order: 'id' },
  }[table];
  const { clauses, values } = filterSQL(query, config.filters, config.keywords);
  const limit = table === 'transfer_logs' ? ` LIMIT ${boundedInt(query.limit, 100)}` : '';
  return all(db, `SELECT * FROM ${table}` + where(clauses) + ` ORDER BY ${config.order}` + limit, values);
}

export async function listStrains(db, name = null) {
  const result = await db.batch([
    db.prepare('SELECT * FROM strains ORDER BY name'),
    db.prepare("SELECT strain,COUNT(*) AS n FROM mice WHERE strain!='' GROUP BY strain"),
    db.prepare("SELECT strain,COUNT(*) AS n FROM cages WHERE strain!='' GROUP BY strain"),
  ]);
  const mice = new Map(result[1].results.map(row => [row.strain, row.n]));
  const cages = new Map(result[2].results.map(row => [row.strain, row.n]));
  const strains = new Map(result[0].results.map(row => [row.name, { ...row, notes: row.notes || '', mouse_count: mice.get(row.name) || 0 }]));
  for (const [strain, count] of mice) if (!strains.has(strain)) strains.set(strain, { id: null, name: strain, notes: '', mouse_count: count });
  if (name !== null) {
    const canonical = normalizeStrain(new Store({ strains: result[0].results }), name, false);
    return { ...(strains.get(canonical) || { id: null, name: canonical, notes: '', mouse_count: 0 }), cage_count: cages.get(canonical) || 0 };
  }
  return [...strains.values()].filter(row => !['/', '无', '-', 'None', 'nan', ''].includes(row.name)).sort((a, b) => a.name.localeCompare(b.name));
}

export async function dashboard(db) {
  const result = await db.batch([
    db.prepare(`SELECT COUNT(*) AS total_mice,COALESCE(SUM(cage_id IS NOT NULL),0) AS in_cage_mice,COALESCE(SUM(owner_id IS NOT NULL),0) AS claimed_mice,
      COALESCE(SUM(cage_id IS NOT NULL AND owner_id IS NULL),0) AS unclaimed_mice FROM mice`),
    db.prepare(`SELECT (SELECT COUNT(*) FROM cages) AS total_cages,(SELECT COUNT(*) FROM claimers) AS total_claimers,
      (SELECT COUNT(*) FROM primers) AS total_primers,(SELECT COUNT(*) FROM genotype_records) AS total_genotypes,
      (SELECT COUNT(*) FROM transfer_requests WHERE status IN ('申请中','进行中')) AS pending_requests_count`),
    db.prepare(`SELECT c.room,COUNT(*) AS cages,r.category FROM cages c LEFT JOIN rooms r ON r.name=c.room
      WHERE c.room!='' GROUP BY c.room,r.category`),
    db.prepare(`SELECT * FROM transfer_requests WHERE status IN ('申请中','进行中') ORDER BY id DESC LIMIT 8`),
  ]);
  const categoryOrder = new Map([['繁育鼠房', 0], ['临时鼠房', 1], ['实验鼠房', 2]]);
  const rooms = result[2].results
    .map(row => ({ ...row, category: row.category === '使用鼠房' ? '实验鼠房' : row.category || roomCategory(row.room) }))
    .sort((a, b) => (categoryOrder.get(a.category) ?? 3) - (categoryOrder.get(b.category) ?? 3) || a.room.localeCompare(b.room, 'zh-CN'));
  return { ...result[0].results[0], ...result[1].results[0], rooms, pending_requests: result[3].results };
}
