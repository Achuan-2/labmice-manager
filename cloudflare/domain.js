import { clean, codes, fail, required, boundedInt, today } from './database.js';
import { strainMap } from './strain-map.js';

export const PRESET_COLORS = ['#2563eb', '#059669', '#d97706', '#7c3aed', '#db2777', '#0891b2', '#ea580c', '#4f46e5', '#16a34a', '#c026d3', '#e11d48', '#0d9488'];
export const EUTHANASIA_OWNER_NAME = '安乐死';
export const byName = (a, b) => String(a.name ?? '').localeCompare(String(b.name ?? ''), 'zh-CN');
export const descending = (a, b) => b.id - a.id;
export const contains = (value, query) => clean(value).toLowerCase().includes(clean(query).toLowerCase());
const invalidStrains = new Set(['', '/', '无', '-', 'None', 'nan', '不详', '不明']);

export function ensureClaimer(store, name, room = null) {
  name = required(name, '领取人姓名', 64);
  let person = store.find('claimers', row => row.name === name);
  if (!person) {
    const used = new Set(store.list('claimers').map(row => row.color));
    const color = PRESET_COLORS.find(value => !used.has(value)) || PRESET_COLORS[store.list('claimers').length % PRESET_COLORS.length];
    person = store.add('claimers', name === EUTHANASIA_OWNER_NAME
      ? { name, role: '其他', color: '#6b7280', notes: '系统默认领取人；选择后小鼠状态自动变为死亡' }
      : { name, default_room: room, color });
  }
  return person;
}

export function ensureCage(store, cageCode, room = '默认鼠房', strain = '', gender = 'M') {
  cageCode = required(cageCode, '笼位编号', 64);
  room = required(room || '默认鼠房', '鼠房名称', 64);
  return store.find('cages', row => row.cage_code === cageCode && row.room === room)
    || store.add('cages', { cage_code: cageCode, room, strain, gender });
}

export function normalizeStrain(store, raw, register = true) {
  const name = clean(raw);
  if (invalidStrains.has(name)) return '';
  const target = strainMap[name.toLowerCase()] || store.find('strains', row => row.name.toLowerCase() === name.toLowerCase())?.name || name;
  if (register && !store.find('strains', row => row.name === target)) store.add('strains', { name: target });
  return target;
}

export function parseParents(store, value) {
  const raw = clean(value);
  const unchanged = { raw, normalized: raw, has_changes: false, details: [] };
  if (!raw || ['新品系引入', '外购', '无', '不明', '不详', '集萃', '常州卡文斯', '邓娟组', '/', '-', '无耳标'].some(text => raw.includes(text))) return unchanged;
  const details = raw.split(/[+、/,，\s\\]+/).filter(Boolean).map(token => {
    const match = token.match(/^([A-Za-z0-9_-]+?)([MFmf])$/);
    let code = token, gender = null;
    if (match && !['HO', 'KO', 'CAS', 'GF', 'BF', 'WT'].includes(match[1].toUpperCase())) {
      code = match[1]; gender = match[2].toUpperCase();
    }
    const mouse = store.find('mice', row => row.mouse_code.toLowerCase() === code.toLowerCase());
    if (mouse) { code = mouse.mouse_code; gender ||= ['M', 'F'].includes(mouse.gender) ? mouse.gender : null; }
    return { raw: token, code, gender, found: Boolean(mouse), role: gender === 'M' ? 'father' : gender === 'F' ? 'mother' : 'parent' };
  });
  let normalized = raw;
  if (details.some(item => item.gender)) normalized = ['M', 'F', null].map(gender => details.filter(item => item.gender === gender).map(item => item.code + (gender || '')).join('、')).filter(Boolean).join('+');
  return { raw, normalized, has_changes: normalized !== raw, details };
}

export const DEFAULT_STATUSES = [
  ['在笼', true, false, 0], ['已领用', true, false, 1], ['繁育中', false, false, 2],
  ['实验中', false, false, 3], ['待鉴定', false, false, 4], ['出笼', true, true, 10000], ['死亡', false, true, 10001],
];
export function ensureStatus(store, value) {
  const name = required(value, '状态名称', 32);
  if (['淘汰', '档案记录'].includes(name)) fail(400, `“${name}”已移除，请使用“出笼”或其他状态`);
  let status = store.find('mouse_statuses', row => row.name === name);
  if (!status) {
    const defaults = DEFAULT_STATUSES.find(item => item[0] === name);
    status = store.add('mouse_statuses', { name, is_system: defaults?.[1] || false, removes_from_cage: defaults?.[2] || false, sort_order: defaults?.[3] ?? store.list('mouse_statuses').length + 5 });
  }
  return status;
}
export function applyStatus(store, mouse, value) {
  let status = ensureStatus(store, value);
  if (status.name === '已领用' && !mouse.cage_id) status = ensureStatus(store, '出笼');
  mouse.status = status.name;
  if (status.removes_from_cage) mouse.cage_id = null;
}
export function applyOwnerStatus(store, mouse) {
  if (clean(mouse.owner_name) !== EUTHANASIA_OWNER_NAME) return false;
  const owner = ensureClaimer(store, EUTHANASIA_OWNER_NAME);
  mouse.owner_id = owner.id; mouse.owner_name = owner.name;
  applyStatus(store, mouse, '死亡');
  return true;
}
export function enrichMouse(store, mouse, history = false) {
  const cage = store.readOnly ? store.cagesById.get(mouse.cage_id) : store.find('cages', row => row.id === mouse.cage_id);
  const date = /^\d{4}-\d{1,2}-\d{1,2}$/.test(mouse.dob || '') ? Date.parse(mouse.dob) : NaN;
  const age_days = Number.isFinite(date) ? Math.max(0, Math.floor((Date.parse(today()) - date) / 86400000)) : null;
  const linked = store.readOnly ? store.genotypesByMouse.get(mouse.id) || [] : store.list('genotype_records').filter(row => row.mouse_id === mouse.id);
  const genotypes = (linked.length ? linked : history ? store.list('genotype_records').filter(row => row.mouse_code === mouse.mouse_code) : []).map(row => ({ ...row, parents: row.parents || mouse.parents }));
  const transfer_logs = history ? store.list('transfer_logs').filter(row => codes(row.mouse_codes).includes(mouse.mouse_code)).sort(descending).slice(0, 15) : [];
  return { ...mouse, cage_code: cage?.cage_code ?? null, cage_room: cage?.room ?? mouse.source_room, age_days, age_weeks: age_days === null ? null : Math.round(age_days / 7 * 10) / 10, genotypes, transfer_logs };
}
export function mouseByCode(store, value) {
  const code = required(value, '耳标编号', 64);
  const mouse = store.find('mice', row => row.mouse_code === code) || store.find('mice', row => contains(row.mouse_code, code));
  if (mouse) return enrichMouse(store, mouse, true);
  const gt = store.find('genotype_records', row => row.mouse_code === code);
  if (!gt) fail(404, `未找到耳标 [${code}] 的小鼠档案`);
  return { ...gt, id: null, status: '出笼', cage_id: null, cage_code: null, cage_room: null, owner_id: null, owner_name: null, age_days: null, age_weeks: null, genotypes: [gt], transfer_logs: [] };
}

export function nextAvailableMouseCode(store, value) {
  const code = required(value, '耳标编号', 64);
  if (!store.find('mice', row => row.mouse_code === code)) return code;
  for (let suffixNumber = 2; ; suffixNumber++) {
    const suffix = `_${suffixNumber}`;
    const candidate = `${code.slice(0, 64 - suffix.length)}${suffix}`;
    if (!store.find('mice', row => row.mouse_code === candidate)) return candidate;
  }
}

export function saveMouse(store, data, existing = null) {
  const updates = store.fields('mice', data);
  if (!existing || 'mouse_code' in data) {
    updates.mouse_code = required(data.mouse_code, '耳标编号', 64);
    const conflict = store.find('mice', row => row.mouse_code === updates.mouse_code && row.id !== existing?.id);
    if (conflict) {
      if (existing) fail(409, `耳标编号 ${updates.mouse_code} 已存在`);
      updates.mouse_code = nextAvailableMouseCode(store, updates.mouse_code);
    }
  }
  if ('strain' in data) updates.strain = normalizeStrain(store, data.strain);
  if ('parents' in data) updates.parents = data.parents ? parseParents(store, data.parents).normalized : data.parents;
  const working = { ...existing, ...updates };
  if ('cage_code' in data) {
    working.cage_id = clean(data.cage_code) ? ensureCage(store, data.cage_code, data.source_room || existing?.source_room || store.find('cages', row => row.id === existing?.cage_id)?.room, working.strain).id : null;
  }
  if (working.cage_id != null) store.get('cages', working.cage_id);
  if ('owner_name' in data) {
    const owner = clean(data.owner_name) ? ensureClaimer(store, data.owner_name) : null;
    working.owner_id = owner?.id ?? null; working.owner_name = owner?.name ?? null;
  } else if ('owner_id' in data) {
    const owner = data.owner_id ? store.get('claimers', data.owner_id) : null;
    working.owner_id = owner?.id ?? null; working.owner_name = owner?.name ?? null;
  }
  if (!existing) {
    working.gender ||= '未知';
    working.status ||= working.cage_id ? '在笼' : '出笼';
    if (!working.cage_id && ['在笼', '已领用'].includes(working.status)) working.status = '出笼';
  } else if (!data.status && ('cage_code' in data || 'cage_id' in data)) {
    if (!working.cage_id) working.status = '出笼';
    else if (working.status === '出笼') working.status = working.owner_id || working.owner_name ? '已领用' : '在笼';
  }
  if (working.status) applyStatus(store, working, working.status);
  applyOwnerStatus(store, working);
  const oldCode = existing?.mouse_code;
  const mouse = existing ? store.update('mice', existing, working) : store.add('mice', working);
  for (const gt of store.list('genotype_records')) {
    if (gt.mouse_id === mouse.id || (oldCode && gt.mouse_code === oldCode)) gt.mouse_code = mouse.mouse_code;
    if (!gt.mouse_id && gt.mouse_code === mouse.mouse_code) gt.mouse_id = mouse.id;
  }
  return mouse;
}

export function batchCreate(store, data) {
  const values = codes(data.mouse_codes);
  if (!values.length || values.length > 500) fail(422, '每次请提供 1–500 个耳标编号');
  const created_codes = [], renamed_codes = [];
  for (const requestedCode of values) {
    const mouse = saveMouse(store, { ...data, mouse_code: requestedCode, gender: data.gender || 'M' });
    created_codes.push(mouse.mouse_code);
    if (mouse.mouse_code !== requestedCode) renamed_codes.push({ original_code: requestedCode, new_code: mouse.mouse_code });
  }
  const renameDetails = renamed_codes.map(item => `${item.original_code} → ${item.new_code}`).join(', ');
  return {
    success: true,
    created_count: created_codes.length,
    created_codes,
    skipped_codes: [],
    renamed_codes,
    message: `成功批量新增 ${created_codes.length} 只小鼠${renameDetails ? `（重复耳标已自动更名: ${renameDetails}）` : ''}`,
  };
}
export function batchUpdateFields(store, data) {
  const ids = [...new Set((data.mouse_ids || []).map(Number).filter(Number.isInteger))];
  if (!ids.length) fail(400, '请至少选择一只小鼠');
  if (ids.length > 500) fail(400, '每次最多批量编辑 500 只小鼠');
  const updateDob = Object.prototype.hasOwnProperty.call(data, 'dob');
  const updateGender = Object.prototype.hasOwnProperty.call(data, 'gender');
  if (!updateDob && !updateGender) fail(400, '请至少选择一个要修改的字段');
  if (updateGender && !['M', 'F', '未知'].includes(data.gender)) fail(400, '请选择有效的性别');
  let dob = null;
  if (updateDob && data.dob) {
    dob = clean(data.dob);
    const parsed = new Date(`${dob}T00:00:00Z`);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(dob) || Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== dob) fail(400, '出生日期格式无效');
  }
  const mice = ids.map(id => store.get('mice', id));
  for (const mouse of mice) store.update('mice', mouse, {
    ...(updateDob ? { dob } : {}),
    ...(updateGender ? { gender: data.gender } : {}),
  });
  return { success: true, affected_count: mice.length, message: `成功批量更新 ${mice.length} 只小鼠` };
}
export function deleteMouse(store, mouse) {
  for (const gt of [...store.list('genotype_records')]) if (gt.mouse_id === mouse.id) store.remove('genotype_records', gt);
  for (const assignment of [...store.list('transfer_request_assignments')]) if (assignment.mouse_id === mouse.id) store.remove('transfer_request_assignments', assignment);
  store.remove('mice', mouse);
}
export function addLog(store, operator, data) {
  return store.add('transfer_logs', { operator, date: today(), status: '已完成', ...data });
}
export function batchMice(store, action, data, operator) {
  const ids = new Set(data.mouse_ids || []), selectedCodes = new Set(codes(data.mouse_codes));
  if (!ids.size && !selectedCodes.size) fail(422, '请至少选择一只小鼠');
  if (ids.size + selectedCodes.size > 500) fail(422, '每次最多处理 500 只小鼠');
  const mice = store.list('mice').filter(row => ids.size ? ids.has(row.id) : selectedCodes.has(row.mouse_code));
  if (!mice.length) fail(404, '未找到匹配的小鼠');
  const owner = action === 'batch-set-owner' ? ensureClaimer(store, data.owner_name, data.target_room) : null;
  if (action === 'batch-transfer') required(data.target_room, '目标鼠房', 64);
  const cage = data.target_cage_code && data.target_room ? ensureCage(store, data.target_cage_code, data.target_room, mice[0].strain, mice[0].gender) : null;
  const groups = new Map();
  for (const mouse of mice) {
    const original = store.find('cages', row => row.id === mouse.cage_id);
    const source = [original?.room || mouse.source_room, original?.cage_code || null];
    const key = JSON.stringify(source);
    if (!groups.has(key)) groups.set(key, { source, codes: [] });
    groups.get(key).codes.push(mouse.mouse_code);
    if (owner) { mouse.owner_id = owner.id; mouse.owner_name = owner.name; mouse.claim_date = data.claim_date || today(); if (data.claim_purpose) mouse.claim_purpose = data.claim_purpose; }
    if (cage) mouse.cage_id = cage.id;
    if (data.target_room) mouse.source_room = data.target_room;
    const status = data.status || (owner ? '已领用' : null);
    if (status) applyStatus(store, mouse, status);
    applyOwnerStatus(store, mouse);
    if (action === 'batch-update-status' && data.notes) mouse.notes = `${mouse.notes || ''} [${today()} ${data.status}: ${data.notes}]`.trim();
    store.update('mice', mouse, {});
  }
  for (const { source, codes: groupCodes } of groups.values()) addLog(store, operator, {
    action_type: action === 'batch-set-owner' ? '设置领取人' : action === 'batch-transfer' ? '转房/换笼' : '状态变更',
    mouse_codes: groupCodes.join(', '), mouse_count: groupCodes.length, claimer_name: owner?.name || null,
    source_room: source[0], source_cage: source[1], target_room: data.target_room || source[0], target_cage: cage?.cage_code || null,
    date: data.claim_date || today(), notes: data.notes || (owner ? `批量指派领取人: ${owner.name}; 目的: ${data.claim_purpose || '无'}` : `批量操作: ${data.status || data.target_room}`),
  });
  return { success: true, affected_count: mice.length, affected_codes: mice.map(row => row.mouse_code), message: `已更新 ${mice.length} 只小鼠` };
}

export function createGenotype(store, data, operator) {
  const code = required(data.mouse_code, '耳标编号', 64);
  if (/[,，、\n]/.test(code)) fail(422, '每条鉴定记录需提供一个有效耳标编号');
  const mouse = store.find('mice', row => row.mouse_code === code);
  const row = store.add('genotype_records', { ...data, mouse_code: code, mouse_id: mouse?.id ?? null,
    test_date: data.test_date || today(), strain: data.strain || mouse?.strain || '', dob: data.dob || mouse?.dob || null,
    gender: data.gender || mouse?.gender || null, parents: data.parents || mouse?.parents || null,
    op_record: data.op_record || operator });
  if (mouse) {
    if (data.genotype_1 && !mouse.genotype_1) mouse.genotype_1 = data.genotype_1;
    if (data.genotype_2 && !mouse.genotype_2) mouse.genotype_2 = data.genotype_2;
    if (data.gender && mouse.gender === '未知') mouse.gender = data.gender;
  }
  return row;
}

const STATE_FIELDS = ['cage_id', 'status', 'owner_id', 'owner_name', 'claim_date', 'source_room'];
const mouseState = mouse => Object.fromEntries(STATE_FIELDS.map(key => [key, mouse[key] ?? null]));
const equalState = (a, b) => STATE_FIELDS.every(key => (a[key] ?? null) === (b[key] ?? null));

export function reconcileAssignments(store, request, updates, operator) {
  let nextStatus = updates.status ?? request.status;
  const selectedCodes = codes(updates.mouse_codes ?? request.mouse_codes);
  if (nextStatus === '已转' && !selectedCodes.length && request.status === '已转' && codes(request.mouse_codes).length) nextStatus = updates.status = '进行中';
  if (nextStatus === '已转' && !selectedCodes.length) fail(400, '审批为已转时，请至少选择或输入一个小鼠编号');
  const desired = new Set(nextStatus === '已转' ? selectedCodes : []);
  const active = new Map(store.list('transfer_request_assignments').filter(row => row.request_id === request.id).map(assignment => {
    const mouse = store.find('mice', row => row.id === assignment.mouse_id);
    return [mouse?.mouse_code, { assignment, mouse }];
  }).filter(([code]) => code));
  const previous = new Set(request.status === '已转' ? codes(request.mouse_codes) : []);
  const legacyRemoved = [...previous].filter(code => !active.has(code) && !desired.has(code));
  if (legacyRemoved.length) fail(409, `以下历史分配没有审批前快照，无法自动恢复，请先核对原笼位和领取信息：${legacyRemoved.join(', ')}`);
  const selected = [...desired].map(code => {
    const mouse = store.find('mice', row => row.mouse_code === code);
    if (!mouse) fail(400, `小鼠编号不存在：${code}`);
    return mouse;
  });
  const added = selected.filter(mouse => !active.has(mouse.mouse_code));
  for (const mouse of added) {
    if (store.find('transfer_request_assignments', row => row.mouse_id === mouse.id)) fail(409, `小鼠 ${mouse.mouse_code} 已分配给其他转鼠申请`);
    if (!mouse.cage_id || ['出笼', '死亡'].includes(mouse.status) || !store.find('cages', row => row.id === mouse.cage_id)) fail(400, `小鼠 ${mouse.mouse_code} 已出笼或死亡，不能分配`);
    if ((mouse.owner_id || mouse.owner_name || mouse.status === '已领用') && !previous.has(mouse.mouse_code)) fail(409, `小鼠 ${mouse.mouse_code} 已有领取人，不能重复分配`);
  }
  const removed = [...active].filter(([code]) => !desired.has(code)).map(([, pair]) => pair);
  const retained = [...active].filter(([code]) => desired.has(code)).map(([, pair]) => pair);
  const demander = clean(updates.demander ?? request.demander);
  if (desired.size && !demander) fail(400, '需求者姓名不能为空');
  const recipientChanged = demander !== clean(request.demander);
  for (const { assignment, mouse } of [...removed, ...(recipientChanged ? retained : [])]) {
    if (!equalState(mouseState(mouse), assignment.assigned_state)) fail(409, `小鼠 ${mouse.mouse_code} 的笼位、状态或领取信息已被其他操作修改，请先核对后再撤销或改派`);
  }
  for (const { assignment, mouse } of removed) {
    const cage = store.find('cages', row => row.id === assignment.original_state.cage_id);
    if (!cage || cage.room !== assignment.source_room || cage.cage_code !== assignment.source_cage) fail(409, `小鼠 ${mouse.mouse_code} 的原笼位已删除或变更，请先恢复原笼位再撤销分配`);
    if (assignment.original_state.owner_id && !store.find('claimers', row => row.id === assignment.original_state.owner_id)) fail(409, `小鼠 ${mouse.mouse_code} 的原领取人已删除，请先核对领取信息`);
  }
  const logGroups = new Map();
  const log = (mouse, action, sourceRoom, sourceCage, targetRoom = null, targetCage = null) => {
    const key = JSON.stringify([action, sourceRoom, sourceCage, targetRoom, targetCage, mouse.owner_name]);
    if (logGroups.has(key)) { const entry = logGroups.get(key); entry.mouse_codes += `, ${mouse.mouse_code}`; entry.mouse_count++; return; }
    logGroups.set(key, addLog(store, operator, { action_type: action, mouse_codes: mouse.mouse_code, mouse_count: 1, claimer_name: mouse.owner_name,
      source_room: sourceRoom, source_cage: sourceCage, target_room: targetRoom, target_cage: targetCage,
      notes: `申请 #${request.seq || request.id}; ${action === '转鼠/审批处理' ? '审批通过，自动出笼' : action}; 反馈: ${updates.feedback ?? request.feedback ?? '无'}` }));
  };
  for (const { assignment, mouse } of removed) {
    store.update('mice', mouse, assignment.original_state);
    log(mouse, '撤销分配/回笼', null, null, assignment.source_room, assignment.source_cage);
    store.remove('transfer_request_assignments', assignment);
  }
  if (desired.size && (added.length || recipientChanged)) {
    const person = ensureClaimer(store, demander);
    for (const mouse of added) {
      const cage = store.get('cages', mouse.cage_id);
      const original_state = mouseState(mouse);
      store.update('mice', mouse, { owner_id: person.id, owner_name: person.name, claim_date: today(), source_room: cage.room, status: '出笼', cage_id: null });
      applyOwnerStatus(store, mouse);
      store.add('transfer_request_assignments', { request_id: request.id, mouse_id: mouse.id, original_state, assigned_state: mouseState(mouse), source_room: cage.room, source_cage: cage.cage_code });
      log(mouse, '转鼠/审批处理', cage.room, cage.cage_code, updates.target_room ?? request.target_room);
    }
    if (recipientChanged) for (const { assignment, mouse } of retained) {
      store.update('mice', mouse, { owner_id: person.id, owner_name: person.name });
      applyOwnerStatus(store, mouse);
      assignment.assigned_state = mouseState(mouse);
      log(mouse, '转鼠/改派领取人', assignment.source_room, assignment.source_cage, updates.target_room ?? request.target_room);
    }
  }
  if ('mouse_codes' in updates || nextStatus === '已转') updates.mouse_codes = selectedCodes.join(', ');
}
