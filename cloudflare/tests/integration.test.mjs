import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import app from '../worker.js';
import { Store, today } from '../database.js';
import { DEFAULT_STATUSES } from '../domain.js';
import { hashPassword, verifyPassword } from '../auth.js';
import { databaseBytes, readDatabase } from '../backup.js';
import { importWorkbook } from '../excel.js';
import { TestDatabase } from './sqlite-adapter.mjs';
import { utils } from 'xlsx';

let db, env, adminToken, guestToken;
const api = async (path, method = 'GET', data, token = adminToken) => {
  const response = await app.request(`http://localhost/api${path}`, {
    method,
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(data !== undefined ? { 'Content-Type': 'application/json' } : {}) },
    body: data !== undefined ? JSON.stringify(data) : undefined,
  }, env);
  const body = response.headers.get('Content-Type')?.includes('json') ? await response.json() : await response.arrayBuffer();
  return { status: response.status, body, response };
};
before(async () => {
  db = new TestDatabase(); env = { DB: db, SECRET_KEY: 'test-secret-key-at-least-32-characters-for-integration' };
  const store = await Store.load(db);
  store.add('users', { username: 'admin', hashed_password: await hashPassword('test-admin-password'), role: 'admin', display_name: '管理员', is_active: true });
  store.add('users', { username: 'guest', hashed_password: await hashPassword('test-guest-password'), role: 'guest', is_active: true });
  for (const [name, is_system, removes_from_cage, sort_order] of DEFAULT_STATUSES) store.add('mouse_statuses', { name, is_system, removes_from_cage, sort_order });
  store.add('rooms', { name: '鼠房甲', category: '实验鼠房' });
  store.add('rooms', { name: '鼠房乙', category: '繁育鼠房' });
  store.add('cages', { cage_code: 'A1', room: '鼠房甲', strain: '5xFAD' });
  store.add('cages', { cage_code: 'A1', room: '鼠房乙', strain: '5xFAD' });
  for (let i = 0; i < 6; i++) store.add('mice', { mouse_code: `M${i}`, cage_id: i % 2 + 1, status: '在笼', strain: '5xFAD', source_room: '原始来源', dob: '2026-01-01', parents: i < 2 ? 'SIRE-1M+DAM-1F' : i === 2 ? 'SIRE-2M+DAM-2F' : null });
  await store.commit(db);
  adminToken = (await api('/auth/login', 'POST', { username: 'ADMIN', password: 'test-admin-password' }, null)).body.access_token;
  guestToken = (await api('/auth/login', 'POST', { username: 'guest', password: 'test-guest-password' }, null)).body.access_token;
  assert.ok(adminToken); assert.ok(guestToken);
});
after(() => db.close());

test('public health, protected reads/writes and removed default password backdoor', async () => {
  assert.equal((await api('/health', 'GET', undefined, null)).status, 200);
  assert.equal((await api('/mice', 'GET', undefined, null)).status, 401);
  assert.equal((await api('/mice', 'POST', { mouse_code: 'BAD' }, guestToken)).status, 403);
  assert.equal((await api('/auth/login', 'POST', { username: 'admin', password: 'admin123' }, null)).status, 401);
  assert.equal((await api('/auth/login', 'POST', { username: 'admin', password: 'test-admin-password' }, null)).status, 200);
  assert.equal((await api('/auth/admins', 'GET', undefined, guestToken)).status, 403);
  assert.ok((await api('/auth/admins')).body.every(row => !('hashed_password' in row)));
});
test('group name defaults publicly and only admins can update it', async () => {
  const initial = await api('/settings/public', 'GET', undefined, null);
  assert.equal(initial.status, 200);
  assert.deepEqual(initial.body, { group_name: '课题组', system_name: '课题组小鼠管理系统' });
  assert.equal((await api('/settings', 'PUT', { group_name: '无权限修改' }, guestToken)).status, 403);
  const updated = await api('/settings', 'PUT', { group_name: ' 神经环路课题组 ' });
  assert.equal(updated.status, 200);
  assert.deepEqual(updated.body, { group_name: '神经环路课题组', system_name: '神经环路课题组小鼠管理系统' });
  assert.equal((await api('/health', 'GET', undefined, null)).body.system, '神经环路课题组小鼠管理系统');
});
test('pagination, filters, joined cage/genotype data, detail and missing API routes', async () => {
  const result = await api('/mice?page=1&page_size=2&strain=5xFAD');
  assert.equal(result.status, 200); assert.equal(result.body.total, 6); assert.equal(result.body.items.length, 2);
  assert.equal(result.body.items[0].cage_code, 'A1'); assert.ok(result.body.items[0].age_weeks > 1);
  assert.equal((await api('/mice?page=0')).status, 422);
  assert.equal((await api('/mice?in_cage=invalid')).status, 422);
  assert.equal((await api('/mice?mouse_code=M0')).body.total, 1);
  assert.deepEqual((await api('/mice/all-parents')).body, ['DAM-1F', 'DAM-2F', 'SIRE-1M', 'SIRE-2M']);
  assert.equal((await api('/mice?parents=SIRE-1M')).body.total, 2);
  assert.equal((await api('/mice?parents=SIRE-1M,DAM-2F')).body.total, 3);
  assert.equal((await api('/mice?parents=SIRE-10M')).body.total, 0);
  assert.equal((await api('/mice/by-code/M0')).body.mouse_code, 'M0');
  assert.equal((await api('/missing-endpoint')).status, 404);
});
test('new mice with duplicate codes receive incrementing suffixes', async () => {
  const single = await api('/mice', 'POST', { mouse_code: 'M0' });
  assert.equal(single.status, 200);
  assert.equal(single.body.mouse_code, 'M0_2');

  const batch = await api('/mice/batch-create', 'POST', { mouse_codes: ['M0', 'M0_2', 'UNIQUE-MOUSE'] });
  assert.equal(batch.status, 200);
  assert.deepEqual(batch.body.created_codes, ['M0_3', 'M0_2_2', 'UNIQUE-MOUSE']);
  assert.deepEqual(batch.body.skipped_codes, []);
  assert.deepEqual(batch.body.renamed_codes, [
    { original_code: 'M0', new_code: 'M0_3' },
    { original_code: 'M0_2', new_code: 'M0_2_2' },
  ]);
  for (const code of ['M0_2', ...batch.body.created_codes]) {
    const mouse = (await api(`/mice/by-code/${code}`)).body;
    assert.equal((await api(`/mice/${mouse.id}`, 'DELETE')).status, 200);
  }
});
test('batch editing changes dates and genders atomically', async () => {
  const first = (await api('/mice/by-code/M4')).body;
  const second = (await api('/mice/by-code/M5')).body;
  const updated = await api('/mice/batch-update-fields', 'POST', {
    mouse_ids: [first.id, second.id], dob: '2026-02-03', gender: 'F',
  });
  assert.equal(updated.status, 200); assert.equal(updated.body.affected_count, 2);
  assert.equal((await api('/mice/by-code/M4')).body.dob, '2026-02-03');
  assert.equal((await api('/mice/by-code/M5')).body.gender, 'F');

  const invalid = await api('/mice/batch-update-fields', 'POST', {
    mouse_ids: [first.id, second.id], dob: '2026-02-30', gender: 'M',
  });
  assert.equal(invalid.status, 400);
  assert.equal((await api('/mice/by-code/M4')).body.gender, 'F');
  assert.equal((await api('/mice/by-code/M5')).body.gender, 'F');
});
test('batch assigning recipients retains cages until out-of-cage status', async () => {
  const result = await api('/mice/batch-set-owner', 'POST', { mouse_codes: ['M5'], owner_name: '领取人甲' });
  assert.equal(result.status, 200);
  let mouse = (await api('/mice/by-code/M5')).body;
  assert.equal(mouse.cage_id, 2); assert.equal(mouse.status, '已领用'); assert.equal(mouse.owner_name, '领取人甲');
  assert.equal((await api('/mice/batch-update-status', 'POST', { mouse_ids: [mouse.id], status: '出笼' })).status, 200);
  mouse = (await api('/mice/by-code/M5')).body;
  assert.equal(mouse.cage_id, null); assert.equal(mouse.transfer_logs[0].source_cage, 'A1');
});
test('default euthanasia recipient forces death and removes mice from cages', async () => {
  const members = (await api('/members')).body;
  const euthanasia = members.find(person => person.name === '安乐死');
  assert.ok(euthanasia);
  assert.equal(members.at(-1).name, '安乐死');
  const mouse = (await api('/mice/by-code/M4')).body;
  assert.notEqual(mouse.cage_id, null);
  const result = await api('/mice/batch-set-owner', 'POST', { mouse_ids: [mouse.id], owner_name: '安乐死', status: '在笼' });
  assert.equal(result.status, 200);
  const updated = (await api('/mice/by-code/M4')).body;
  assert.equal(updated.owner_name, '安乐死'); assert.equal(updated.owner_id, euthanasia.id);
  assert.equal(updated.status, '死亡'); assert.equal(updated.cage_id, null);
  assert.equal((await api(`/members/${euthanasia.id}`, 'DELETE')).status, 400);
});
let requestId;
test('guest request submission, approval snapshot, grouped logs and safe rollback', async () => {
  const request = await api('/transfer-requests', 'POST', { demander: '审批领取人', strain: '废鼠', target_room: '东五' }, guestToken);
  assert.equal(request.status, 200); requestId = request.body.id;
  assert.equal((await api(`/transfer-requests/${requestId}`, 'PUT', { status: '已转', mouse_codes: 'M0, M1, M2' })).status, 200);
  const assigned = await api(`/transfer-requests/${requestId}/assigned-mice`);
  assert.equal(assigned.body.length, 3);
  assert.ok(assigned.body.every(mouse => mouse.cage_id === null && mouse.assignment_source_cage === 'A1'));
  const mouse = (await api('/mice/by-code/M0')).body;
  assert.equal(mouse.transfer_logs[0].source_room, '鼠房甲'); assert.equal(mouse.transfer_logs[0].mouse_count, 2);
  assert.equal((await api(`/transfer-requests/${requestId}`, 'PUT', { mouse_codes: 'M0, M2' })).status, 200);
  const restored = (await api('/mice/by-code/M1')).body;
  assert.equal(restored.cage_id, 2); assert.equal(restored.owner_id, null); assert.equal(restored.source_room, '原始来源');
});
test('failed approval containing an unknown mouse saves no assignments or recipients', async () => {
  const request = (await api('/transfer-requests', 'POST', { demander: '不得保存的人', strain: '测试' })).body;
  const before = (await api('/members')).body.length;
  assert.equal((await api(`/transfer-requests/${request.id}`, 'PUT', { status: '已转', mouse_codes: 'M3, DOES-NOT-EXIST' })).status, 400);
  assert.equal((await api('/mice/by-code/M3')).body.cage_id, 2);
  assert.equal((await api('/members')).body.length, before);
});
test('independent changes block stale approval reversal without partial rollback', async () => {
  const mouse = (await api('/mice/by-code/M0')).body;
  assert.equal((await api(`/mice/${mouse.id}`, 'PUT', { source_room: '人工修改' })).status, 200);
  const failure = await api(`/transfer-requests/${requestId}`, 'PUT', { status: '取消' });
  assert.equal(failure.status, 409);
  assert.equal((await api('/mice/by-code/M2')).body.cage_id, null);
  await api(`/mice/${mouse.id}`, 'PUT', { source_room: '鼠房甲' });
  assert.equal((await api(`/transfer-requests/${requestId}`, 'DELETE')).status, 200);
  assert.equal((await api('/mice/by-code/M0')).body.cage_id, 1);
  assert.equal((await api('/mice/by-code/M2')).body.cage_id, 1);
});
test('optimistic concurrency guard rejects an entire stale transaction', async () => {
  const first = await Store.load(db), stale = await Store.load(db);
  first.get('mice', 4).notes = '第一位管理员';
  await first.commit(db);
  stale.get('mice', 4).notes = '不应该保存';
  stale.add('claimers', { name: '回滚的成员' });
  await assert.rejects(() => stale.commit(db), error => error.status === 409);
  const current = await Store.load(db);
  assert.equal(current.get('mice', 4).notes, '第一位管理员');
  assert.equal(current.find('claimers', row => row.name === '回滚的成员'), undefined);
});
test('genotype batch is atomic, links mice and follows renamed mouse codes', async () => {
  assert.equal((await api('/genotypes/batch', 'POST', [{ mouse_code: 'M0', genotype_1: 'HET' }, { mouse_code: 'M1', genotype_1: 'WT' }])).status, 200);
  assert.equal((await api('/mice/by-code/M0')).body.genotypes.length, 1);
  assert.equal((await api('/genotypes?page=1&page_size=1')).body.total, 2);
  const before = (await api('/genotypes?page=1')).body.total;
  assert.equal((await api('/genotypes/batch', 'POST', [{ mouse_code: 'M2' }, { mouse_code: 'A,B' }])).status, 422);
  assert.equal((await api('/genotypes?page=1')).body.total, before);
  assert.equal((await api('/mice/1', 'PUT', { mouse_code: 'NEW-M0' })).status, 200);
  assert.equal((await api('/genotypes/by-mouse/NEW-M0')).body.length, 1);
});
test('cage deletion/room protection, strain with slash, statuses and stats', async () => {
  assert.equal((await api('/cages/rooms/' + encodeURIComponent('鼠房甲'), 'DELETE')).status, 400);
  assert.equal((await api('/strains', 'POST', { name: 'TRAP2/AI9', notes: '背景' })).status, 200);
  assert.equal((await api('/strains/Trap2%2FAi9')).body.notes, '背景');
  assert.equal((await api('/strains/Trap2%2FAi9', 'PUT', { notes: '已更新' })).status, 200);
  assert.equal((await api('/strains/Trap2%2FAi9')).body.notes, '已更新');
  const status = (await api('/mouse-statuses', 'POST', { name: '观察中' })).body;
  await api('/mice/4', 'PUT', { status: '观察中' });
  assert.equal((await api(`/mouse-statuses/${status.id}`, 'DELETE')).status, 409);
  assert.equal((await api(`/mouse-statuses/${status.id}`, 'DELETE', { replacement_status: '出笼' })).status, 200);
  assert.equal((await api('/mice/4')).body.cage_id, null);
  const stats = (await api('/stats/dashboard')).body;
  assert.equal(stats.total_mice, 6); assert.equal(stats.total_genotypes, 2);
  assert.deepEqual(stats.rooms.map(room => room.room), ['鼠房乙', '鼠房甲']);
  assert.deepEqual(stats.rooms.map(room => room.category), ['繁育鼠房', '实验鼠房']);
  assert.ok((await api('/cages/rooms?include_categories=true')).body.every(row => row.category));
});
test('SQLite backup round trip preserves all tables, accounts and assignment JSON', async () => {
  const current = await Store.load(db), bytes = await databaseBytes(current.rows), restored = await readDatabase(bytes);
  for (const table of Object.keys(current.rows)) assert.deepEqual(restored[table], current.rows[table], table);
  assert.equal(await verifyPassword('test-admin-password', restored.users[0].hashed_password), true);
  assert.equal((await api('/import-export/database/export', 'GET', undefined, guestToken)).status, 403);
  await assert.rejects(() => readDatabase(new Uint8Array([1, 2, 3])), error => error.status === 400);
});
test('restore keeps a durable safety backup and validates before changing any data', async () => {
  const bytes = await databaseBytes((await Store.load(db)).rows);
  const form = new FormData(); form.set('file', new File([bytes], 'backup.db'));
  const response = await app.request('http://localhost/api/import-export/database/restore', { method: 'POST', headers: { Authorization: `Bearer ${adminToken}` }, body: form }, env);
  assert.equal(response.status, 200, await response.clone().text());
  const body = await response.json(); assert.ok(body.safety_backup);
  const list = await api('/import-export/database/backups'); assert.equal(list.body[0].backup_id, body.safety_backup);
  const backup = await api(`/import-export/database/backups/${body.safety_backup}`); assert.equal(backup.status, 200);
  assert.equal((await readDatabase(backup.body)).mice.length, 6);
});
test('Excel import keeps recipients on blank cells, skips historical sheets and is repeatable', async () => {
  const store = await Store.load(db);
  const workbook = utils.book_new();
  const cageRows = [['笼位', '品系', '', '性别', '耳标1', '耳标2'], ['Z1', '5FAD', '', 'M', 'IMPORT-1', 'IMPORT-2']];
  utils.book_append_sheet(workbook, utils.aoa_to_sheet(cageRows), '小鼠笼位信息');
  utils.book_append_sheet(workbook, utils.aoa_to_sheet([['基因', '编号', '性别', '生日'], ['5xFAD', 'SHOULD-NOT-IMPORT', 'M', '2026-01-01']]), '繁育小鼠');
  const first = importWorkbook(store, workbook);
  assert.equal(first.mice_imported, 2);
  assert.equal(store.find('mice', row => row.mouse_code === 'SHOULD-NOT-IMPORT'), undefined);
  const mouse = store.find('mice', row => row.mouse_code === 'IMPORT-1');
  mouse.owner_name = '保留领取人';
  const second = importWorkbook(store, workbook);
  assert.equal(second.mice_imported, 0); assert.equal(mouse.owner_name, '保留领取人'); assert.equal(mouse.strain, '5xFAD');
});
test('Excel import extracts compact mating dates from cage notes and preserves both text fields', async () => {
  const store = await Store.load(db);
  const workbook = utils.book_new();
  const header = ['笼位', '品系', '数量', '性别', '编号', null, null, null, null, null, null, null, null, '出生日期', '观察记录', '备注'];
  const row = ['DATE-1', '5xFAD', 1, 'M/F', 'DATE-MOUSE', null, null, null, null, null, null, null, null, '2026-01-01', '状态正常', '合笼日期：260305'];
  utils.book_append_sheet(workbook, utils.aoa_to_sheet([header, row]), '实验动物楼小鼠信息405B-实时更新');
  importWorkbook(store, workbook);
  const cage = store.find('cages', item => item.cage_code === 'DATE-1' && item.room === '实验动物楼405B');
  assert.equal(cage.mating_date, '2026-03-05');
  assert.equal(cage.observation, '状态正常\n合笼日期：260305');
  assert.equal(cage.notes, '合笼日期：260305');
  assert.equal(store.find('mice', item => item.mouse_code === 'DATE-MOUSE').status, '繁育中');
});
test('Excel export produces real XLSX bytes for authenticated guests', async () => {
  for (const resource of ['mice', 'cages']) {
    const response = await api(`/import-export/export/${resource}`, 'GET', undefined, guestToken);
    assert.equal(response.status, 200);
    assert.equal(new Uint8Array(response.body)[0], 0x50);
  }
});
test('cage rename moves mice to the target and keeps the source as an empty cage', async () => {
  const emptySource = (await api('/cages', 'POST', { room: '合并测试房', cage_code: 'G5', strain: '来源品系' })).body;
  await api('/cages', 'POST', { room: '合并测试房', cage_code: 'F5', strain: '空笼品系' });
  await api('/mice', 'POST', { mouse_code: 'MERGE-EMPTY', source_room: '合并测试房', cage_code: 'G5' });
  assert.equal((await api(`/cages/${emptySource.id}`, 'PUT', { cage_code: 'F5' })).status, 200);
  let cages = (await api('/cages?room=' + encodeURIComponent('合并测试房'))).body;
  assert.equal(cages.filter(cage => cage.cage_code === 'F5').length, 1);
  const emptyTarget = cages.find(cage => cage.cage_code === 'F5');
  assert.equal((await api('/mice/by-code/MERGE-EMPTY')).body.cage_id, emptyTarget.id);
  assert.equal(cages.find(cage => cage.id === emptySource.id).mouse_count, 0);
  assert.equal(cages.find(cage => cage.id === emptySource.id).cage_code, 'G5');

  const occupiedSource = (await api('/cages', 'POST', { room: '合并测试房', cage_code: 'G6', strain: '来源品系' })).body;
  const occupiedTarget = (await api('/cages', 'POST', { room: '合并测试房', cage_code: 'F6', strain: '目标品系' })).body;
  await api('/mice', 'POST', { mouse_code: 'MERGE-SOURCE', source_room: '合并测试房', cage_code: 'G6' });
  await api('/mice', 'POST', { mouse_code: 'MERGE-TARGET', source_room: '合并测试房', cage_code: 'F6' });
  const warning = await api(`/cages/${occupiedSource.id}`, 'PUT', { cage_code: 'F6', strain: '合并品系' });
  assert.equal(warning.status, 409);
  assert.match(warning.body.detail, /确认合并/);
  assert.match(warning.body.detail, /将保留为空笼/);
  assert.equal((await api(`/cages/${occupiedSource.id}`, 'PUT', { cage_code: 'F6', strain: '合并品系', merge_existing: true })).status, 200);
  assert.equal((await api('/mice/by-code/MERGE-SOURCE')).body.cage_id, occupiedTarget.id);
  assert.equal((await api('/mice/by-code/MERGE-TARGET')).body.cage_id, occupiedTarget.id);
  cages = (await api('/cages?room=' + encodeURIComponent('合并测试房'))).body;
  assert.equal(cages.filter(cage => cage.cage_code === 'F6').length, 1);
  assert.equal(cages.find(cage => cage.cage_code === 'F6').strain, '合并品系');
  assert.equal(cages.find(cage => cage.id === occupiedSource.id).mouse_count, 0);
  assert.equal(cages.find(cage => cage.id === occupiedSource.id).cage_code, 'G6');
});
test('todo reminders generate automatically, split buckets and preserve linked records', async () => {
  const dateOffset = days => {
    const value = new Date(Date.now() + 8 * 3600_000);
    value.setUTCDate(value.getUTCDate() + days);
    return value.toISOString().slice(0, 10);
  };
  const cage = (await api('/cages', 'POST', { room: '待办测试房', cage_code: 'T1', gender: 'M/F', litter_birth_dates: [dateOffset(-21), dateOffset(-10)] })).body;
  const mouse = (await api('/mice', 'POST', { mouse_code: 'TODO-OLD', source_room: '待办测试房', cage_code: 'T1', dob: dateOffset(-281), gender: 'F' })).body;
  let todayTodos = (await api('/todos?bucket=today')).body;
  assert.deepEqual(new Set(todayTodos.map(todo => todo.source)), new Set(['litter_weaning', 'mixed_aged']));
  assert.ok(todayTodos.every(todo => !todo.due_at.includes('T')));
  assert.ok(todayTodos.every(todo => todo.cage.id === cage.id));
  assert.equal((await api('/todos?bucket=today')).body.length, 2);
  const futureAutomatic = (await api('/todos?bucket=future')).body;
  assert.equal(futureAutomatic.length, 1);
  assert.ok(!futureAutomatic[0].due_at.includes('T'));
  assert.match(futureAutomatic[0].auto_key, new RegExp(dateOffset(-10)));
  await api('/mice', 'POST', { mouse_code: 'TODO-LITTER', source_room: '待办测试房', cage_code: 'T1', dob: dateOffset(-10), gender: '未知' });
  await api('/mice', 'POST', { mouse_code: 'TODO-LITTER-2', source_room: '待办测试房', cage_code: 'T1', dob: dateOffset(-10), gender: '未知' });
  assert.equal((await api(`/cages/${cage.id}`, 'PUT', { litter_birth_dates: [dateOffset(-21)] })).status, 400);
  const duplicateSplit = await api('/mice/batch-split-transfer', 'POST', { groups: [
    { mouse_ids: [(await api('/mice/by-code/TODO-LITTER')).body.id], target_room: '待办测试房', target_cage_code: 'X1' },
    { mouse_ids: [(await api('/mice/by-code/TODO-LITTER')).body.id], target_room: '待办测试房', target_cage_code: 'Y1' },
  ] });
  assert.equal(duplicateSplit.status, 400);
  const litterMouse = (await api('/mice/by-code/TODO-LITTER')).body;
  const litterMouse2 = (await api('/mice/by-code/TODO-LITTER-2')).body;
  const split = await api('/mice/batch-split-transfer', 'POST', { groups: [
    { mouse_ids: [litterMouse.id], target_room: '待办测试房', target_cage_code: 'X1' },
    { mouse_ids: [litterMouse2.id], target_room: '待办测试房', target_cage_code: 'Y1' },
  ] });
  assert.equal(split.status, 200);
  assert.equal((await api('/mice/by-code/TODO-LITTER')).body.cage_code, 'X1');
  assert.equal((await api('/mice/by-code/TODO-LITTER-2')).body.cage_code, 'Y1');

  const secondCage = (await api('/cages', 'POST', { room: '待办测试房', cage_code: 'T2', gender: 'M' })).body;
  const secondMouse = (await api('/mice', 'POST', { mouse_code: 'TODO-SECOND', source_room: '待办测试房', cage_code: 'T2', gender: 'M' })).body;
  const manualToday = (await api('/todos', 'POST', { title: '今天处理', due_at: `${dateOffset(0)}T15:30`, cage_ids: [cage.id, secondCage.id], mouse_ids: [mouse.id, secondMouse.id], notes: '测试备注' })).body;
  const manualInbox = (await api('/todos', 'POST', { title: '稍后安排' })).body;
  todayTodos = (await api('/todos?bucket=today')).body;
  const inboxTodos = (await api('/todos?bucket=inbox')).body;
  assert.ok(todayTodos.some(todo => todo.id === manualToday.id && todo.mouse.mouse_code === 'TODO-OLD'));
  assert.deepEqual(manualToday.cage_ids, [cage.id, secondCage.id]);
  assert.deepEqual(manualToday.mouse_ids, [mouse.id, secondMouse.id]);
  assert.deepEqual(manualToday.cages.map(item => item.cage_code), ['T1', 'T2']);
  assert.deepEqual(manualToday.mice.map(item => item.mouse_code), ['TODO-OLD', 'TODO-SECOND']);
  const updatedManual = (await api(`/todos/${manualToday.id}`, 'PUT', { cage_ids: [secondCage.id], mouse_ids: [] })).body;
  assert.deepEqual(updatedManual.cage_ids, [secondCage.id]);
  assert.deepEqual(updatedManual.mouse_ids, []);
  assert.equal(updatedManual.mouse, null);
  assert.ok(inboxTodos.some(todo => todo.id === manualInbox.id));

  const automatic = todayTodos.find(todo => todo.source !== 'manual');
  assert.equal((await api(`/todos/${automatic.id}`, 'DELETE')).status, 200);
  assert.ok(!(await api('/todos?bucket=today')).body.some(todo => todo.id === automatic.id));
  assert.equal((await api(`/todos/${manualInbox.id}`, 'DELETE')).status, 200);
});
