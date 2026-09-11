import { Hono } from 'hono';
import { meterDatabase } from './meter.js';
import { bodyLimit } from 'hono/body-limit';
import { Store, ApiError, all, fail, clean, required, boundedInt, codes, today, decodeRow } from './database.js';
import { admin, authenticate, login, publicUser, hashPassword, verifyPassword } from './auth.js';
import { enrichMouse, parseParents, saveMouse, deleteMouse, batchCreate, batchUpdateFields, batchMice, createGenotype,
  reconcileAssignments, ensureStatus, normalizeStrain, PRESET_COLORS, addLog, EUTHANASIA_OWNER_NAME, applyOwnerStatus } from './domain.js';
import { listMice, getMouse, listCages, rooms, listGenotypes, members, simpleList, listStrains, listParents, dashboard, roomCategory } from './queries.js';
import { exportDatabase, restoreDatabase, backupList, downloadBackup } from './backup.js';
import { uploadExcel, exportExcel } from './excel.js';

const app = new Hono();
const DEFAULT_GROUP_NAME = '课题组';
const publicSettings = async db => {
  const setting = await db.prepare("SELECT value FROM system_settings WHERE key='group_name'").first();
  const groupName = clean(setting?.value) || DEFAULT_GROUP_NAME;
  return { group_name: groupName, system_name: `${groupName}小鼠管理系统` };
};
app.use('/api/*', async (c, next) => {
  const metered = meterDatabase(c.env.DB);
  c.env = { ...c.env, DB: metered.db };
  await next();
  if (c.get('user')?.role === 'admin') {
    c.header('X-D1-Rows-Read', String(metered.usage.rows_read));
    c.header('X-D1-Rows-Written', String(metered.usage.rows_written));
  }
  console.log(JSON.stringify({ event: 'd1_usage', method: c.req.method, path: c.req.path, ...metered.usage }));
});
app.use('/api/*', bodyLimit({ maxSize: 20 * 1024 * 1024, onError: c => c.json({ detail: '单次上传不能超过 20 MB' }, 413) }));
app.use('/api/*', async (c, next) => {
  c.header('Cache-Control', 'no-store');
  c.header('X-Content-Type-Options', 'nosniff');
  await next();
});
app.onError((error, c) => {
  if (error instanceof ApiError) return c.json({ detail: error.message }, error.status);
  if (error instanceof SyntaxError) return c.json({ detail: '请求数据格式不正确' }, 400);
  console.error('API failure', c.req.method, c.req.path, error.message);
  return c.json({ detail: '服务器处理失败，请稍后重试' }, 500);
});
app.get('/api/health', async c => {
  await c.env.DB.prepare('SELECT 1').first();
  const settings = await publicSettings(c.env.DB);
  return c.json({ status: 'ok', system: settings.system_name, version: '1.2.0', database: 'D1', deployment: 'cloudflare' });
});
app.get('/api/settings/public', async c => c.json(await publicSettings(c.env.DB)));
app.post('/api/auth/login', async c => {
  const ip = c.req.header('CF-Connecting-IP') || 'local';
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(ip));
  const key = Array.from(new Uint8Array(digest), x => x.toString(16).padStart(2, '0')).join('');
  const window = Math.floor(Date.now() / 900000);
  const result = await c.env.DB.batch([
    c.env.DB.prepare('DELETE FROM _login_attempts WHERE window < ?').bind(window - 1),
    c.env.DB.prepare('INSERT INTO _login_attempts(key,window,attempts) VALUES(?,?,1) ON CONFLICT(key,window) DO UPDATE SET attempts=attempts+1 RETURNING attempts').bind(key, window),
  ]);
  if (result[1].results[0].attempts > 30) fail(429, '登录尝试过于频繁，请 15 分钟后重试');
  return c.json(await login(c.env.DB, c.env, await c.req.json()));
});
app.get('/api/auth/me', async c => {
  if (!c.req.header('Authorization')) return c.json({ role: 'guest', username: '游客', display_name: '访客模式 (只读)', is_authenticated: false });
  const user = await authenticate(c.req.raw, c.env.DB, c.env);
  return c.json({ id: user.id, role: user.role, username: user.username, display_name: user.display_name || user.username, is_authenticated: true });
});
app.use('/api/*', async (c, next) => {
  c.set('user', await authenticate(c.req.raw, c.env.DB, c.env));
  await next();
});

function mutate(handler, allowMember = false) {
  return async c => {
    const authenticated = c.get('user');
    if (!allowMember) admin(authenticated);
    // Independent editors do not need mice/genotypes or other laboratory tables.
    const table = c.req.path.startsWith('/api/primers') ? 'primers'
      : c.req.path.startsWith('/api/auth/admins') ? 'users' : null;
    const store = await Store.load(c.env.DB, table ? [...new Set(['users', table])] : undefined);
    const user = store.find('users', row => row.id === authenticated.id && row.is_active);
    if (!user) fail(401, '登录已失效');
    if (!allowMember) admin(user);
    const text = await c.req.text();
    const data = text ? JSON.parse(text) : {};
    const result = await handler(store, data, c, user);
    await store.commit(c.env.DB);
    return c.json(result);
  };
}
const operator = user => user.display_name || user.username;
const message = text => ({ success: true, message: text });

app.put('/api/settings', async c => {
  admin(c.get('user'));
  const groupName = required((await c.req.json()).group_name, '课题组名称', 64);
  await c.env.DB.prepare(
    "INSERT INTO system_settings(id,key,value,updated_at) VALUES(1,'group_name',?,datetime('now')) " +
    "ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at"
  ).bind(groupName).run();
  return c.json(await publicSettings(c.env.DB));
});

app.get('/api/auth/admins', async c => { admin(c.get('user')); return c.json((await all(c.env.DB, 'SELECT * FROM users ORDER BY id')).map(publicUser)); });
app.post('/api/auth/admins', mutate(async (store, data) => {
  const username = required(data.username, '用户名', 64);
  const password = required(data.password, '密码', 256);
  const role = data.role || 'admin';
  if (!['admin', 'guest'].includes(role)) fail(400, '请选择管理员或普通用户角色');
  if (store.find('users', row => row.username.toLowerCase() === username.toLowerCase())) fail(409, '该用户名已存在');
  return publicUser(store.add('users', { username, hashed_password: await hashPassword(password), role, display_name: clean(data.display_name) || username, is_active: true }));
}));
app.put('/api/auth/admins/:id/password', mutate(async (store, data, c) => {
  const user = store.get('users', c.req.param('id'));
  if (data.old_password && !await verifyPassword(data.old_password, user.hashed_password)) fail(400, '原密码不正确');
  user.hashed_password = await hashPassword(required(data.new_password, '新密码', 256));
  return message('密码修改成功');
}));
app.delete('/api/auth/admins/:id', mutate((store, data, c, user) => {
  const target = store.get('users', c.req.param('id'));
  if (target.id === user.id) fail(400, '不能删除当前正在登录的管理员账号');
  if (target.role === 'admin' && store.list('users').filter(row => row.role === 'admin' && row.is_active).length <= 1) fail(400, '系统必须保留至少一个管理员账号');
  store.remove('users', target); return message('删除成功');
}));

app.get('/api/mice', async c => c.json(await listMice(c.env.DB, c.req.query())));
app.get('/api/mice/all-strains', async c => c.json((await all(c.env.DB, "SELECT DISTINCT strain FROM mice WHERE strain IS NOT NULL AND strain!='' ORDER BY strain")).map(row => row.strain)));
app.get('/api/mice/all-parents', async c => c.json(await listParents(c.env.DB)));
app.get('/api/mice/by-code/:code', async c => c.json(await getMouse(c.env.DB, c.req.param('code'), true)));
app.get('/api/mice/:id', async c => c.json(await getMouse(c.env.DB, boundedInt(c.req.param('id'), null, Number.MAX_SAFE_INTEGER))));
app.post('/api/mice/parse-parents', async c => {
  const data = await c.req.json();
  const parentCodes = clean(data.parents).split(/[+、/,，\s\\]+/).flatMap(code => [code.toLowerCase(), code.replace(/[MFmf]$/, '').toLowerCase()]);
  const mice = await all(c.env.DB, 'SELECT * FROM mice WHERE lower(mouse_code) IN (SELECT value FROM json_each(?))', [JSON.stringify(parentCodes)]);
  return c.json(parseParents(new Store({ mice }), data.parents));
});
app.post('/api/mice', mutate((store, data) => enrichMouse(store, saveMouse(store, data))));
app.post('/api/mice/batch-create', mutate((store, data) => batchCreate(store, data)));
app.post('/api/mice/batch-update-fields', mutate((store, data) => batchUpdateFields(store, data)));
app.post('/api/mice/batch-split-transfer', mutate((store, data, c, user) => {
  if (!Array.isArray(data.groups) || !data.groups.length) fail(400, '请至少设置一个分笼目标');
  const allIds = data.groups.flatMap(group => Array.isArray(group.mouse_ids) ? group.mouse_ids.map(Number) : []);
  if (!allIds.length) fail(400, '请至少选择一只小鼠');
  if (allIds.length !== new Set(allIds).size) fail(400, '同一只小鼠不能分配到多个目标笼位');
  if (allIds.length > 500) fail(400, '每次最多批量换笼 500 只小鼠');
  for (const id of allIds) store.get('mice', id);
  let affected = 0;
  for (const group of data.groups) {
    if (!Array.isArray(group.mouse_ids) || !group.mouse_ids.length) fail(400, '每个目标笼位至少需要一只小鼠');
    const targetRoom = required(group.target_room, '目标鼠房', 64);
    const targetCageCode = required(group.target_cage_code, '目标笼位', 64);
    const groupMice = group.mouse_ids.map(id => store.get('mice', id));
    if (groupMice.some(mouse => {
      const cage = store.find('cages', row => row.id === mouse.cage_id);
      return cage?.room === targetRoom && cage?.cage_code === targetCageCode;
    })) fail(400, `目标笼位 ${targetRoom} · ${targetCageCode} 不能与小鼠当前笼位相同`);
    batchMice(store, 'batch-transfer', {
      mouse_ids: group.mouse_ids,
      target_room: targetRoom,
      target_cage_code: targetCageCode,
      notes: data.notes || '生鼠批次满21天批量换笼',
    }, operator(user));
    affected += group.mouse_ids.length;
  }
  return { success: true, affected_count: affected, message: `成功将 ${affected} 只小鼠分配到 ${data.groups.length} 个目标笼位` };
}));
app.put('/api/mice/:id', mutate((store, data, c) => enrichMouse(store, saveMouse(store, data, store.get('mice', c.req.param('id'))), true)));
app.delete('/api/mice/:id', mutate((store, data, c) => { deleteMouse(store, store.get('mice', c.req.param('id'))); return message('删除成功'); }));
for (const action of ['batch-set-owner', 'batch-transfer', 'batch-update-status']) app.post(`/api/mice/${action}`, mutate((store, data, c, user) => batchMice(store, action, data, operator(user))));

app.get('/api/cages/rooms', async c => c.json(await rooms(c.env.DB, c.req.query())));
app.post('/api/cages/rooms', mutate((store, data) => {
  const name = required(data.name, '鼠房名称', 64);
  const category = data.category === '使用鼠房' ? '实验鼠房' : data.category || roomCategory(name);
  if (!['繁育鼠房', '临时鼠房', '实验鼠房'].includes(category)) fail(400, '请选择有效的鼠房分类');
  const room = store.find('rooms', row => row.name === name);
  if (!room) store.add('rooms', { name, category, description: data.description });
  else if (data.category) room.category = category;
  return { ...message(`成功添加鼠房 [${name}]`), name };
}));
app.delete('/api/cages/rooms/:name', mutate((store, data, c) => {
  const name = c.req.param('name'), room = store.find('rooms', row => row.name === name);
  const cages = store.list('cages').filter(row => row.room === name), ids = new Set(cages.map(row => row.id));
  if (!room && !cages.length) fail(404, '鼠房未找到');
  if (store.list('mice').some(row => ids.has(row.cage_id))) fail(400, '鼠房内仍有小鼠，请先将全部小鼠转移后再删除');
  for (const cage of cages) store.remove('cages', cage);
  if (room) store.remove('rooms', room);
  return message('鼠房及空笼位已删除');
}));
app.get('/api/cages', async c => c.json(await listCages(c.env.DB, c.req.query())));
app.get('/api/cages/:id', async c => c.json(await listCages(c.env.DB, {}, boundedInt(c.req.param('id'), null, Number.MAX_SAFE_INTEGER))));
const normalizeLitterDates = (values, legacy = null) => {
  const candidates = Array.isArray(values) ? values : (legacy ? [legacy] : []);
  if (candidates.length > 100) fail(422, '单个笼位最多记录 100 个生鼠批次');
  const normalized = [];
  for (const candidate of candidates) {
    const value = clean(candidate);
    if (!value) continue;
    const parsed = new Date(`${value}T00:00:00Z`);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value) || Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== value) fail(400, '生鼠日期格式无效');
    if (!normalized.includes(value)) normalized.push(value);
  }
  return normalized.sort().reverse();
};
const saveCage = (store, data, row = null) => {
  const merged = { ...row, ...data };
  merged.cage_code = required(merged.cage_code, '笼位编号', 64);
  merged.room = required(merged.room || '默认鼠房', '鼠房名称', 64);
  merged.capacity = boundedInt(merged.capacity, 5, 1000);
  if ('litter_birth_dates' in data) {
    merged.litter_birth_dates = normalizeLitterDates(data.litter_birth_dates);
    merged.litter_birth_date = merged.litter_birth_dates[0] || null;
  } else if ('litter_birth_date' in data) {
    merged.litter_birth_dates = normalizeLitterDates(null, data.litter_birth_date);
    merged.litter_birth_date = merged.litter_birth_dates[0] || null;
  } else {
    merged.litter_birth_dates = normalizeLitterDates(merged.litter_birth_dates, merged.litter_birth_date);
  }
  if (row) {
    const removedDates = normalizeLitterDates(row.litter_birth_dates, row.litter_birth_date).filter(date => !merged.litter_birth_dates.includes(date));
    if (removedDates.length && store.list('mice').some(mouse => mouse.cage_id === row.id && removedDates.includes(mouse.dob))) fail(400, '生鼠批次已绑定在笼小鼠，请先修改小鼠出生日期或移出本笼');
  }
  const existing = store.find('cages', cage => cage.cage_code === merged.cage_code && cage.room === merged.room && cage.id !== row?.id);
  if (existing) {
    const existingMice = store.list('mice').filter(mouse => mouse.cage_id === existing.id);
    if (existingMice.length && !data.merge_existing) fail(409, `目标笼位 [${merged.room} · ${merged.cage_code}] 已有 ${existingMice.length} 只小鼠。确认合并后，两笼小鼠将进入目标笼位，原笼位 [${row.room} · ${row.cage_code}] 将保留为空笼。`);
    for (const mouse of store.list('mice')) if (mouse.cage_id === row.id) mouse.cage_id = existing.id;
    store.update('cages', existing, merged);
    return existing;
  }
  return row ? store.update('cages', row, merged) : store.add('cages', merged);
};
app.post('/api/cages', mutate((store, data) => saveCage(store, data)));
app.put('/api/cages/:id', mutate((store, data, c) => saveCage(store, data, store.get('cages', c.req.param('id')))));
app.delete('/api/cages/:id', mutate((store, data, c) => {
  const cage = store.get('cages', c.req.param('id'));
  for (const mouse of store.list('mice')) if (mouse.cage_id === cage.id) { mouse.cage_id = null; mouse.status = '出笼'; mouse.source_room ||= cage.room; }
  store.remove('cages', cage); return message('笼位删除成功');
}));

const mixedCage = cage => ['M/F', '混合'].includes(cage.gender);
const dateOnly = value => /^\d{4}-\d{2}-\d{2}/.test(clean(value)) ? clean(value).slice(0, 10) : null;
const addDays = (date, days) => {
  const value = new Date(`${date}T00:00:00Z`);
  value.setUTCDate(value.getUTCDate() + days);
  return value.toISOString().slice(0, 10);
};
const validDueAt = value => {
  const result = clean(value) || null;
  if (result && !/^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2})?$/.test(result)) fail(400, '待办时间格式无效');
  return result;
};
const relationIds = (store, table, values, legacyId) => {
  const source = values !== undefined ? (Array.isArray(values) ? values : values == null ? [] : [values]) : (legacyId ? [legacyId] : []);
  const ids = [...new Set(source.map(value => boundedInt(value, null, Number.MAX_SAFE_INTEGER)))];
  for (const id of ids) store.get(table, id);
  return ids;
};
function syncAutomaticTodos(store) {
  const currentDate = today(), active = new Map();
  const cages = store.list('cages'), mice = store.list('mice');
  for (const cage of cages.filter(mixedCage)) {
    for (const birthDate of normalizeLitterDates(cage.litter_birth_dates, cage.litter_birth_date)) {
      const dueDate = addDays(birthDate, 21);
      active.set(`litter-weaning:${cage.id}:${birthDate}`, {
        title: `笼位 ${cage.room} · ${cage.cage_code}：生鼠满21天，请进行分笼`, due_at: dueDate,
        notes: `生鼠日期：${birthDate}。请检查幼鼠并完成断奶、分笼及档案更新。`, cage_id: cage.id, cage_ids: [cage.id], source: 'litter_weaning',
      });
    }
    const aged = mice.filter(mouse => mouse.cage_id === cage.id && dateOnly(mouse.dob) && addDays(dateOnly(mouse.dob), 280) < currentDate);
    if (aged.length) {
      const weeks = Math.max(...aged.map(mouse => Math.floor((Date.parse(`${currentDate}T00:00:00Z`) - Date.parse(`${dateOnly(mouse.dob)}T00:00:00Z`)) / 604800000)));
      active.set(`mixed-aged:${cage.id}`, {
        title: `笼位 ${cage.room} · ${cage.cage_code}：混笼小鼠超过40周`, due_at: currentDate,
        notes: `超过40周的小鼠：${aged.map(mouse => mouse.mouse_code).join('、')}；最大周龄约 ${weeks} 周。请检查并处理该混笼。`, cage_id: cage.id, cage_ids: [cage.id], source: 'mixed_aged',
      });
    }
  }
  const existing = new Map(store.list('todo_reminders').filter(todo => todo.auto_key).map(todo => [todo.auto_key, todo]));
  for (const [key, values] of active) {
    const todo = existing.get(key);
    if (!todo) store.add('todo_reminders', { ...values, auto_key: key, status: 'pending' });
    else if (todo.status === 'pending') store.update('todo_reminders', todo, values);
  }
  for (const [key, todo] of existing) if (todo.status === 'pending' && !active.has(key)) store.update('todo_reminders', todo, { status: 'completed', completed_at: new Date().toISOString() });
}
const todoView = (store, todo) => {
  const cages = [...new Set((Array.isArray(todo.cage_ids) ? todo.cage_ids : todo.cage_id ? [todo.cage_id] : []).map(Number))].map(id => store.find('cages', cage => cage.id === id)).filter(Boolean).map(cage => ({ id: cage.id, room: cage.room, cage_code: cage.cage_code }));
  const mice = [...new Set((Array.isArray(todo.mouse_ids) ? todo.mouse_ids : todo.mouse_id ? [todo.mouse_id] : []).map(Number))].map(id => store.find('mice', mouse => mouse.id === id)).filter(Boolean).map(mouse => ({ id: mouse.id, mouse_code: mouse.mouse_code }));
  const cageIds = cages.map(cage => cage.id), mouseIds = mice.map(mouse => mouse.id);
  return { ...todo, cage_id: cageIds[0] || null, mouse_id: mouseIds[0] || null, cage_ids: cageIds, mouse_ids: mouseIds, cage: cages[0] || null, mouse: mice[0] || null, cages, mice };
};
app.get('/api/todos', async c => {
  const bucket = c.req.query('bucket') || 'today';
  if (!['today', 'future', 'inbox', 'all'].includes(bucket)) fail(422, '待办分类无效');
  const store = await Store.load(c.env.DB, ['cages', 'mice', 'todo_reminders']);
  syncAutomaticTodos(store);
  await store.commit(c.env.DB);
  let items = store.list('todo_reminders');
  if (c.req.query('include_completed') !== 'true') items = items.filter(todo => todo.status === 'pending');
  const currentDate = today();
  if (bucket === 'today') items = items.filter(todo => todo.due_at && todo.due_at.slice(0, 10) <= currentDate);
  if (bucket === 'future') items = items.filter(todo => todo.due_at && todo.due_at.slice(0, 10) > currentDate);
  if (bucket === 'inbox') items = items.filter(todo => !todo.due_at || todo.due_at.slice(0, 10) > currentDate);
  items.sort((a, b) => (a.due_at || '9999').localeCompare(b.due_at || '9999') || b.id - a.id);
  return c.json(items.map(todo => todoView(store, todo)));
});
app.post('/api/todos', mutate((store, data) => {
  const cageIds = relationIds(store, 'cages', data.cage_ids, data.cage_id);
  const mouseIds = relationIds(store, 'mice', data.mouse_ids, data.mouse_id);
  return todoView(store, store.add('todo_reminders', { title: required(data.title, '待办内容', 256), due_at: validDueAt(data.due_at), notes: clean(data.notes) || null, cage_id: cageIds[0] || null, mouse_id: mouseIds[0] || null, cage_ids: cageIds, mouse_ids: mouseIds, source: 'manual', status: 'pending' }));
}));
app.put('/api/todos/:id', mutate((store, data, c) => {
  const todo = store.get('todo_reminders', c.req.param('id')), updates = { ...data };
  if ('title' in updates) updates.title = required(updates.title, '待办内容', 256);
  if ('due_at' in updates) updates.due_at = validDueAt(updates.due_at);
  if ('status' in updates) {
    if (!['pending', 'completed'].includes(updates.status)) fail(400, '待办状态无效');
    updates.completed_at = updates.status === 'completed' ? new Date().toISOString() : null;
  }
  if ('cage_ids' in updates || 'cage_id' in updates) {
    const cageIds = relationIds(store, 'cages', 'cage_ids' in updates ? updates.cage_ids : undefined, updates.cage_id);
    updates.cage_ids = cageIds; updates.cage_id = cageIds[0] || null;
  }
  if ('mouse_ids' in updates || 'mouse_id' in updates) {
    const mouseIds = relationIds(store, 'mice', 'mouse_ids' in updates ? updates.mouse_ids : undefined, updates.mouse_id);
    updates.mouse_ids = mouseIds; updates.mouse_id = mouseIds[0] || null;
  }
  return todoView(store, store.update('todo_reminders', todo, updates));
}));
app.delete('/api/todos/:id', mutate((store, data, c) => {
  const todo = store.get('todo_reminders', c.req.param('id'));
  if (todo.auto_key) store.update('todo_reminders', todo, { status: 'completed', completed_at: new Date().toISOString() });
  else store.remove('todo_reminders', todo);
  return message(todo.auto_key ? '自动提醒已忽略' : '待办已删除');
}));

for (const base of ['/api/members', '/api/claimers']) {
  app.get(base, async c => c.json(await members(c.env.DB)));
  app.get(base + '/:id/mice', async c => {
    const id = boundedInt(c.req.param('id'), null, Number.MAX_SAFE_INTEGER);
    const person = await c.env.DB.prepare('SELECT * FROM claimers WHERE id=?').bind(id).first();
    if (!person) fail(404, '成员未找到');
    const result = await c.env.DB.batch([
      c.env.DB.prepare('SELECT * FROM mice WHERE owner_id=? ORDER BY id DESC').bind(id),
      c.env.DB.prepare('SELECT * FROM cages WHERE id IN (SELECT cage_id FROM mice WHERE owner_id=?)').bind(id),
      c.env.DB.prepare('SELECT * FROM genotype_records WHERE mouse_id IN (SELECT id FROM mice WHERE owner_id=?)').bind(id),
    ]);
    const store = new Store({ mice: result[0].results, cages: result[1].results, genotype_records: result[2].results });
    return c.json({ claimer: { ...person, mouse_count: result[0].results.length }, items: store.list('mice').map(row => enrichMouse(store, row)) });
  });
  app.post(base, mutate((store, data) => {
    const name = required(data.name, '成员姓名', 64);
    if (store.find('claimers', row => row.name === name)) fail(409, '成员已存在');
    return store.add('claimers', { ...data, name, role: data.role === '实验管家' ? '管家' : data.role || '学生', color: clean(data.color) || PRESET_COLORS[store.list('claimers').length % PRESET_COLORS.length] });
  }));
  app.put(base + '/:id', mutate((store, data, c, user) => {
    const person = store.get('claimers', c.req.param('id'));
    if (data.role === '实验管家') data.role = '管家';
    if (user.role !== 'admin' && (('name' in data && data.name !== person.name) || ('role' in data && data.role !== person.role))) fail(403, '普通成员不可修改姓名或身份角色，请联系管理员');
    if ('name' in data) {
      data.name = required(data.name, '成员姓名', 64);
      if (person.name === EUTHANASIA_OWNER_NAME && data.name !== EUTHANASIA_OWNER_NAME) fail(400, '系统默认领取人“安乐死”不可改名');
      if (store.find('claimers', row => row.name === data.name && row.id !== person.id)) fail(409, '该姓名已存在');
      for (const mouse of store.list('mice')) if (mouse.owner_id === person.id) { mouse.owner_name = data.name; applyOwnerStatus(store, mouse); }
    }
    return store.update('claimers', person, data);
  }, true));
  app.delete(base + '/:id', mutate((store, data, c) => {
    const person = store.get('claimers', c.req.param('id'));
    if (person.name === EUTHANASIA_OWNER_NAME) fail(400, '系统默认领取人“安乐死”不可删除');
    for (const mouse of store.list('mice')) if (mouse.owner_id === person.id) { mouse.owner_id = null; mouse.owner_name = null; if (mouse.cage_id && mouse.status === '已领用') mouse.status = '在笼'; }
    store.remove('claimers', person); return message('领取人删除成功，关联小鼠已置为空闲');
  }));
}

app.get('/api/transfer-requests', async c => c.json(await simpleList(c.env.DB, 'transfer_requests', c.req.query())));
app.post('/api/transfer-requests', mutate((store, data, c, user) => {
  const demander = required(data.demander, '需求者姓名', 64), strain = required(data.strain, '品系');
  const target_room = clean(data.target_room || '东五');
  if (!['东四', '东五'].includes(target_room)) fail(400, '转入鼠房仅支持东四或东五');
  return store.add('transfer_requests', { ...data, demander, strain, target_room, cage_count: boundedInt(data.cage_count, 1, 1000),
    seq: String(Math.max(0, ...store.list('transfer_requests').map(row => row.id)) + 1), request_date: data.request_date || today(),
    age_gender_req: data.age_gender_req || '成年/无要求', status: '申请中', handler: operator(user) });
}, true));
app.get('/api/transfer-requests/:id/assigned-mice', async c => {
  admin(c.get('user'));
  const id = boundedInt(c.req.param('id'), null, Number.MAX_SAFE_INTEGER);
  const request = await c.env.DB.prepare('SELECT * FROM transfer_requests WHERE id=?').bind(id).first();
  if (!request) fail(404, '转鼠申请未找到');
  const selected = JSON.stringify(request.status === '已转' ? codes(request.mouse_codes) : []);
  const result = await c.env.DB.batch([
    c.env.DB.prepare('SELECT * FROM mice WHERE mouse_code IN (SELECT value FROM json_each(?))').bind(selected),
    c.env.DB.prepare('SELECT * FROM transfer_request_assignments WHERE request_id=?').bind(id),
    c.env.DB.prepare('SELECT * FROM cages WHERE id IN (SELECT cage_id FROM mice WHERE mouse_code IN (SELECT value FROM json_each(?)))').bind(selected),
    c.env.DB.prepare('SELECT * FROM genotype_records WHERE mouse_code IN (SELECT value FROM json_each(?))').bind(selected),
  ]);
  const store = new Store({ mice: result[0].results, cages: result[2].results, genotype_records: result[3].results });
  return c.json(store.list('mice').map(mouse => {
    const item = enrichMouse(store, mouse), snapshot = result[1].results.find(row => row.mouse_id === mouse.id);
    return { ...item, assignment_source_room: snapshot?.source_room ?? item.cage_room, assignment_source_cage: snapshot?.source_cage ?? item.cage_code, assigned_to_request: true };
  }));
});
app.put('/api/transfer-requests/:id', mutate((store, data, c, user) => {
  const request = store.get('transfer_requests', c.req.param('id'));
  if (data.status && !['申请中', '进行中', '已转', '取消'].includes(data.status)) fail(422, '请选择有效的申请状态');
  reconcileAssignments(store, request, data, operator(user));
  return store.update('transfer_requests', request, { ...data, handler: operator(user) });
}));
app.delete('/api/transfer-requests/:id', mutate((store, data, c, user) => {
  const request = store.get('transfer_requests', c.req.param('id'));
  reconcileAssignments(store, request, { status: '取消' }, operator(user));
  store.remove('transfer_requests', request); return message('转鼠需求已删除');
}));

app.get('/api/genotypes', async c => c.json(await listGenotypes(c.env.DB, c.req.query())));
app.get('/api/genotypes/by-mouse/:code', async c => c.json(await all(c.env.DB, 'SELECT * FROM genotype_records WHERE mouse_code=? ORDER BY id DESC', [c.req.param('code').trim()])));
app.post('/api/genotypes', mutate((store, data, c, user) => createGenotype(store, data, operator(user))));
app.post('/api/genotypes/batch', mutate((store, data, c, user) => {
  if (!Array.isArray(data) || data.length < 1 || data.length > 500) fail(422, '每次请录入 1–500 个耳标编号');
  const values = data.map(row => clean(row.mouse_code));
  if (new Set(values).size !== values.length) fail(422, '耳标编号不能重复');
  return data.map(row => createGenotype(store, row, operator(user)));
}));
app.put('/api/genotypes/:id', mutate((store, data, c) => {
  const { mouse_code, mouse_id, ...updates } = data;
  return store.update('genotype_records', store.get('genotype_records', c.req.param('id')), updates);
}));
app.delete('/api/genotypes/:id', mutate((store, data, c) => { store.remove('genotype_records', store.get('genotype_records', c.req.param('id'))); return message('鉴定记录已删除'); }));

app.get('/api/mouse-statuses', async c => c.json((await all(c.env.DB, 'SELECT s.*,COUNT(m.id) AS usage_count FROM mouse_statuses s LEFT JOIN mice m ON m.status=s.name GROUP BY s.id ORDER BY s.sort_order,s.id')).map(row => decodeRow('mouse_statuses', row))));
app.post('/api/mouse-statuses', mutate((store, data) => {
  if (store.find('mouse_statuses', row => row.name === clean(data.name))) fail(409, '状态已存在');
  return { ...ensureStatus(store, data.name), usage_count: 0 };
}));
app.put('/api/mouse-statuses/:id', mutate((store, data, c) => {
  const row = store.get('mouse_statuses', c.req.param('id'));
  if (row.is_system) fail(400, '系统状态不可重命名');
  const name = required(data.name, '状态名称', 32);
  if (['淘汰', '档案记录'].includes(name)) fail(400, '此状态已移除，请使用其他名称');
  if (store.find('mouse_statuses', status => status.name === name && status.id !== row.id)) fail(409, '状态已存在');
  let usage_count = 0;
  for (const mouse of store.list('mice')) if (mouse.status === row.name) { mouse.status = name; usage_count++; }
  store.update('mouse_statuses', row, { name }); return { ...row, usage_count };
}));
app.delete('/api/mouse-statuses/:id', mutate((store, data, c) => {
  const row = store.get('mouse_statuses', c.req.param('id'));
  if (row.is_system) fail(400, '系统状态不可删除');
  const mice = store.list('mice').filter(mouse => mouse.status === row.name);
  if (mice.length) {
    if (!data.replacement_status) fail(409, `仍有 ${mice.length} 只小鼠使用该状态，请先选择目标状态`);
    const replacement = store.find('mouse_statuses', status => status.name === clean(data.replacement_status) && status.id !== row.id);
    if (!replacement) fail(400, '请选择有效的目标状态');
    for (const mouse of mice) { mouse.status = replacement.name; if (replacement.removes_from_cage) mouse.cage_id = null; }
  }
  store.remove('mouse_statuses', row); return { ...message('状态已删除'), migrated_count: mice.length };
}));

app.get('/api/strains', async c => c.json(await listStrains(c.env.DB)));
app.get('/api/strains/*', async c => c.json(await listStrains(c.env.DB, decodeURIComponent(c.req.path.slice('/api/strains/'.length)))));
const strainWrite = (store, data, name) => {
  const canonical = normalizeStrain(store, required(name, '品系名称'));
  if (!canonical) fail(422, '请输入有效的品系名称');
  const row = store.find('strains', strain => strain.name === canonical);
  if (data.notes !== undefined) store.update('strains', row, { notes: data.notes });
  return { ...row, notes: row.notes || '', mouse_count: store.list('mice').filter(mouse => mouse.strain === canonical).length };
};
app.post('/api/strains', mutate((store, data) => strainWrite(store, data, data.name)));
app.put('/api/strains/*', mutate((store, data, c) => strainWrite(store, data, decodeURIComponent(c.req.path.slice('/api/strains/'.length)))));
app.post('/api/strains/sync/merge-cases', mutate(store => {
  let merged = 0;
  for (const table of ['mice', 'cages', 'genotype_records']) for (const row of store.list(table)) {
    const canonical = normalizeStrain(store, row.strain);
    if (canonical !== (row.strain || '')) { row.strain = canonical; merged++; }
  }
  for (const row of [...store.list('strains')]) {
    const canonical = normalizeStrain(store, row.name);
    if (canonical && canonical !== row.name) {
      const target = store.find('strains', strain => strain.name === canonical);
      if (row.notes && !target.notes) target.notes = row.notes;
      store.remove('strains', row);
    }
  }
  return message(`成功合并规范化品系名称，共更新 ${merged} 条记录`);
}));
app.get('/api/primers', async c => c.json(await simpleList(c.env.DB, 'primers', c.req.query())));
app.post('/api/primers', mutate((store, data) => store.add('primers', { ...data, strain_short: required(data.strain_short, '品系简称') })));
app.put('/api/primers/:id', mutate((store, data, c) => store.update('primers', store.get('primers', c.req.param('id')), data)));
app.delete('/api/primers/:id', mutate((store, data, c) => { store.remove('primers', store.get('primers', c.req.param('id'))); return message('引物删除成功'); }));
app.get('/api/transfers', async c => c.json(await simpleList(c.env.DB, 'transfer_logs', c.req.query())));
app.post('/api/transfers', mutate((store, data, c, user) => addLog(store, operator(user), { ...data, mouse_codes: required(data.mouse_codes, '小鼠编号', 32768), operator: operator(user) })));
app.get('/api/stats/dashboard', async c => c.json(await dashboard(c.env.DB)));

app.get('/api/import-export/database/export', async c => { admin(c.get('user')); return exportDatabase(c.env.DB); });
app.post('/api/import-export/database/restore', async c => { admin(c.get('user')); return c.json(await restoreDatabase(c.env.DB, await c.req.formData())); });
app.get('/api/import-export/database/backups', async c => { admin(c.get('user')); return c.json(await backupList(c.env.DB)); });
app.get('/api/import-export/database/backups/:id', async c => { admin(c.get('user')); return downloadBackup(c.env.DB, c.req.param('id')); });
app.post('/api/import-export/upload', async c => { admin(c.get('user')); return c.json(await uploadExcel(c.env.DB, await c.req.formData())); });
app.post('/api/import-export/init-local', c => c.json({ detail: '云端请使用上传 Excel 功能，支持选择多个文件；本地文件夹导入可在 Docker 版本中使用' }, 400));
app.get('/api/import-export/export/:resource', async c => exportExcel(c.env.DB, c.req.param('resource')));
app.all('/api/*', c => c.json({ detail: 'API 接口未找到' }, 404));
app.all('*', c => c.env.ASSETS.fetch(c.req.raw));
export default app;
