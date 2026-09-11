import { read, write, utils, SSF } from 'xlsx';
import { Store, all, clean, codes, fail, today } from './database.js';
import { ensureCage, ensureClaimer, normalizeStrain, ensureStatus, addLog, parseParents, applyOwnerStatus } from './domain.js';

const empty = value => value == null || ['', '/', '-', '无', 'nan', 'None'].includes(clean(value));
const litterDateText = cage => {
  try {
    const dates = Array.isArray(cage.litter_birth_dates) ? cage.litter_birth_dates : JSON.parse(cage.litter_birth_dates || '[]');
    if (Array.isArray(dates) && dates.length) return dates.join('、');
  } catch {}
  return cage.litter_birth_date || '';
};
const outcomes = new Set(['HOM', 'HET', 'WT', 'WT?', 'HET?', 'HOM?', '？', '?', '+', '-', '+/-', '+/+', '-/-', '纯合', '纯合子', '杂合', '杂合子', '野生', '野生型', '阳性', '阴性', '待鉴定', '待测', '未测', '未鉴定', '已测', 'POS', 'NEG', 'MUT', 'NULL', 'POS/NEG', 'NEG/POS', 'HET/WT', 'HOM/WT']);
const invalidCodes = new Set(['ALDH1L1-CRE', 'ALDH1L1', 'AI148', 'AI93', 'AI9', '5XFAD', 'CAMK-TTA', 'CAMK2A-TTA', 'CMAK-TTA', 'TRAP2', 'TRAP 2', 'PV-CRE', 'RASGRF2', 'TETO', 'TETO-GCAMP6S', 'GCAMP6S', 'CRE', 'PDYN-CRE', 'PDYN', 'SST', 'VIP', 'BFP', 'GFP', 'TDTOMATO', 'TOMATO', 'C57', 'C57BL/6', '编号', '小鼠编号', '耳标', '父母', '基因型', '品系', '生日', 'DOB', '性别', 'GENOTYPE 1', 'GENOTYPE 2', 'GENOTYPE 3', '操作记录', '备注', 'TEST', 'DEMO', '示例', '无耳标', '待', '待分笼', '待查', '无']);
export function validCode(value) {
  const text = clean(value), upper = text.toUpperCase();
  return !empty(value) && !['\\', '?', '？', '已测', '待测', '未知'].includes(text)
    && !outcomes.has(upper) && !invalidCodes.has(upper.replace(/[\s_]+/g, '-')) && !invalidCodes.has(upper)
    && !(text.includes('/') && text.split('/').some(part => invalidCodes.has(part.trim().toUpperCase()) || outcomes.has(part.trim().toUpperCase())));
}
export function parseDate(value) {
  if (empty(value)) return null;
  if (value instanceof Date) return value.toISOString().slice(0, 10);
  if (typeof value === 'number') {
    if (/^\d{6}(?:\d{2})?$/.test(String(value))) return parseDate(String(value));
    const date = SSF.parse_date_code(value);
    return date ? `${date.y}-${String(date.m).padStart(2, '0')}-${String(date.d).padStart(2, '0')}` : null;
  }
  const text = clean(value).replace(/[年月./]/g, '-').replace('日', '');
  const compact = text.match(/^(\d{2}|\d{4})(\d{2})(\d{2})$/);
  const match = compact || text.match(/^(\d{2}|\d{4})-(\d{1,2})-(\d{1,2})$/);
  if (!match) return text;
  const year = Number(match[1]) + (Number(match[1]) < 100 ? 2000 : 0), month = Number(match[2]), day = Number(match[3]);
  const date = new Date(Date.UTC(year, month - 1, day));
  if (date.getUTCFullYear() !== year || date.getUTCMonth() + 1 !== month || date.getUTCDate() !== day) return null;
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
}
export function extractMatingDate(...values) {
  for (const value of values) {
    const match = clean(value).match(/合笼(?:日期|时间)?\s*[：:]\s*(\d{6,8}|\d{2,4}[年./-]\d{1,2}[月./-]\d{1,2}日?)/);
    if (match) return parseDate(match[1]);
  }
  return null;
}
const mergeObservation = (...values) => [...new Set(values.map(clean).filter(Boolean))].join('\n');
function metrics() { return { mice_imported: 0, cages_imported: 0, claimers_imported: 0, transfers_imported: 0, transfer_requests_imported: 0, genotypes_imported: 0, inferred_genders_count: 0, primers_imported: 0, errors: [] }; }
function rowsOf(sheet) {
  const range = utils.decode_range(sheet['!ref'] || 'A1');
  if (range.e.r > 50000 || range.e.c > 200) fail(413, '工作表过大，单表最多支持 50000 行、200 列');
  const rows = utils.sheet_to_json(sheet, { header: 1, defval: null, raw: true, blankrows: true });
  for (const merge of sheet['!merges'] || []) {
    if (merge.e.r > 50000 || merge.e.c > 200) fail(413, '合并单元格范围过大');
    const value = rows[merge.s.r]?.[merge.s.c];
    // Fill down only vertical merged cells; horizontal headers retain their original positions.
    if (merge.s.c === merge.e.c) for (let r = merge.s.r + 1; r <= merge.e.r; r++) {
      rows[r] ||= []; rows[r][merge.s.c] = value;
    }
  }
  return rows;
}
const headerColumn = (header, test, fallback = -1) => { const index = header.findIndex(text => test(clean(text))); return index < 0 ? fallback : index; };
function archiveColumns(header, archive = false) {
  return {
    mouse_code: headerColumn(header, h => /编号|耳标/.test(h), archive ? 5 : -1),
    strain: headerColumn(header, h => ['基因型', '品系', '基因'].includes(h) || h.includes('品系') && !h.includes('编号'), archive ? 1 : -1),
    dob: headerColumn(header, h => /DOB|生日|出生/i.test(h), archive ? 2 : -1),
    gender: headerColumn(header, h => h.includes('性别'), archive ? 3 : -1),
    parents: headerColumn(header, h => /父母|亲代/.test(h), archive ? 4 : -1),
    genotype_1: headerColumn(header, h => /GENOTYPE\s*1|基因型\s*1/i.test(h), archive ? 6 : -1),
    genotype_2: headerColumn(header, h => /GENOTYPE\s*2|基因型\s*2/i.test(h), archive ? 7 : -1),
    genotype_3: headerColumn(header, h => /GENOTYPE\s*3|基因型\s*3/i.test(h)),
    op_record: headerColumn(header, h => h.includes('操作'), archive ? 8 : -1),
    notes: headerColumn(header, h => h.includes('备注'), archive ? 9 : -1),
    test_date: headerColumn(header, h => h.includes('测试日期') || h === '日期', archive ? 0 : -1),
    owner_name: headerColumn(header, h => /拥有者|领取|责任人/.test(h)),
    room: headerColumn(header, h => /所在鼠房|来源鼠房/.test(h) || h === '鼠房'),
    cage_code: headerColumn(header, h => /所在笼位|笼位号/.test(h)),
  };
}
function supplement(mouse, values) {
  for (const [key, value] of Object.entries(values)) if (!empty(value) && (empty(mouse[key]) || key === 'gender' && mouse.gender === '未知')) mouse[key] = value;
}
function parsedValues(store, row, columns) {
  const result = Object.fromEntries(Object.entries(columns).filter(([key]) => !['room', 'cage_code'].includes(key)).map(([key, index]) => [key, index >= 0 && row[index] != null ? clean(row[index]) : null]));
  result.strain = normalizeStrain(store, row[columns.strain]);
  result.dob = parseDate(row[columns.dob]);
  result.test_date = parseDate(row[columns.test_date]);
  return result;
}

export function importWorkbook(store, workbook) {
  const result = metrics(), inferred = new Map();
  const infer = parents => {
    for (const part of clean(parents).replace(/[(（].*?[)）]/g, '').split(/[+、/,，\s\\]+/)) {
      const match = part.match(/^([A-Za-z0-9_-]+?)([MFmf])$/);
      if (match && !['HO', 'CAS', 'GF', 'BF', 'W', 'KO', 'T2'].includes(match[1].toUpperCase())) inferred.set(match[1], match[2].toUpperCase());
    }
  };
  // Preserve laboratory processing order even when the workbook tab order differs.
  const priority = name => name === '小鼠档案' ? 0 : name === '小鼠笼位信息' ? 1 : /基因鉴定|鉴定结果/.test(name) ? 2 : /东四/.test(name) ? 3 : /405B|实验动物楼/.test(name) ? 4 : /转鼠/.test(name) ? 5 : /引物/.test(name) ? 6 : 7;
  let recognized = 0;
  for (const name of [...workbook.SheetNames].sort((a, b) => priority(a) - priority(b))) {
    const rows = rowsOf(workbook.Sheets[name]), header = rows[0] || [];
    const kind = priority(name);
    if (kind === 7 && (name === '繁育小鼠' || name.includes('信息汇总') || ['基因', '编号', '性别', '生日'].every(value => header.map(clean).join(' ').includes(value)))) continue;
    if (kind === 0 || kind === 2 || kind === 7 && /编号|耳标/.test(header.map(clean).join(' ')) && /品系|基因/.test(header.map(clean).join(' '))) {
      recognized++;
      const columns = archiveColumns(header, kind === 0);
      if (columns.mouse_code < 0) fail(400, `工作表 ${name} 缺少耳标/编号列`);
      let carriedDate = null, carriedStrain = '', carriedDob = null;
      for (const row of rows.slice(1)) {
        const values = parsedValues(store, row, columns);
        if (kind === 2) {
          if (values.test_date) { carriedDate = values.test_date; carriedStrain = ''; carriedDob = null; }
          if (values.strain) carriedStrain = values.strain;
          if (values.dob) carriedDob = values.dob;
          values.test_date ||= carriedDate; values.strain ||= carriedStrain; values.dob ||= carriedDob;
        }
        const rawCodes = kind === 7 ? codes(values.mouse_code) : [clean(values.mouse_code)];
        for (const code of rawCodes) {
          if (!validCode(code)) continue;
          infer(values.parents);
          let mouse = store.find('mice', item => item.mouse_code === code);
          const fields = { strain: values.strain, dob: values.dob, gender: values.gender || '未知', parents: values.parents,
            genotype_1: empty(values.genotype_1) ? null : values.genotype_1, genotype_2: empty(values.genotype_2) ? null : values.genotype_2,
            test_date: values.test_date, notes: [kind === 0 ? values.op_record : '', values.notes].filter(Boolean).join(' ') || null };
          if (!mouse) { mouse = store.add('mice', { mouse_code: code, ...fields, status: '出笼', source_room: kind === 0 ? '江湾发育所' : null }); result.mice_imported++; }
          else supplement(mouse, fields);
          if (kind === 0 && /死亡/.test(`${values.op_record || ''} ${values.notes || ''}`)) { mouse.status = '死亡'; mouse.cage_id = null; }
          if (kind === 2) {
            if (!store.find('genotype_records', gt => gt.mouse_code === code && gt.test_date === values.test_date && gt.genotype_1 === fields.genotype_1 && gt.genotype_2 === fields.genotype_2)) {
              store.add('genotype_records', { ...values, ...fields, mouse_code: code, mouse_id: mouse.id, parents: values.parents === code ? '' : values.parents, genotype_3: empty(values.genotype_3) ? null : values.genotype_3 });
              result.genotypes_imported++;
            }
          }
          if (kind === 7) {
            const room = clean(row[columns.room]), cageCode = clean(row[columns.cage_code]);
            if (room && cageCode && !store.find('transfer_request_assignments', item => item.mouse_id === mouse.id)) {
              mouse.cage_id = ensureCage(store, cageCode, room, values.strain, values.gender || '未知').id; mouse.source_room = room;
            }
            if (!empty(values.owner_name) && !mouse.owner_id) {
              const owner = ensureClaimer(store, values.owner_name, room || null); mouse.owner_id = owner.id; mouse.owner_name = owner.name; result.claimers_imported++;
            }
          }
        }
      }
    } else if ([1, 3, 4].includes(kind)) {
      recognized++;
      for (const row of rows.slice(1)) {
        const east = kind === 3, building = kind === 4;
        const cageCode = clean(row[east ? 1 : 0]);
        if (!cageCode) continue;
        const room = east ? `东四${clean(row[0]) || '105'}` : building ? '实验动物楼405B' : '江湾发育所';
        const strain = normalizeStrain(store, row[east ? 2 : 1]), gender = clean(row[east ? 4 : 3]) || 'M';
        const dob = parseDate(row[building ? 13 : 10]);
        const observation = clean(row[building ? 14 : 11]), notes = clean(row[building ? 15 : 12]);
        const matingDate = extractMatingDate(observation, notes);
        const cage = ensureCage(store, cageCode, room, strain, gender);
        supplement(cage, { strain, gender, notes, observation: mergeObservation(observation, notes),
          mating_date: matingDate });
        result.cages_imported++;
        const ownerName = east ? clean(row[11]) : '';
        const owner = ownerName ? ensureClaimer(store, ownerName, room) : null;
        if (owner) result.claimers_imported++;
        const slots = row.slice(east ? 5 : 4, east ? 10 : building ? 13 : 10);
        for (const [index, cell] of slots.entries()) {
          if (empty(cell)) continue;
          for (let code of /无耳标|待/.test(clean(cell)) ? [clean(cell)] : codes(clean(cell).replaceAll('/', ','))) {
            if (!code) continue;
            const ambiguous = /无耳标|待|C57|WT|野生|纯合|杂合|未知/i.test(code) || ['F', 'M'].includes(code);
            if (ambiguous) code = `${code}_${building ? '405B' : east ? '东四' : '江湾'}_${cageCode}_${index + 1}`;
            let mouse = store.find('mice', item => item.mouse_code === code);
            // Excel cannot silently overwrite a live approval or resurrect a dead mouse.
            if (mouse && (mouse.status === '死亡' || store.find('transfer_request_assignments', item => item.mouse_id === mouse.id))) continue;
            if (!mouse) { mouse = store.add('mice', { mouse_code: code, strain, gender, dob, source_room: room, status: building && matingDate ? '繁育中' : '在笼' }); result.mice_imported++; }
            mouse.cage_id = cage.id;
            supplement(mouse, { strain, dob, source_room: room });
            if (owner) { mouse.owner_id = owner.id; mouse.owner_name = owner.name; mouse.status = '已领用'; }
          }
        }
      }
    } else if (kind === 5) {
      recognized++;
      for (const row of rows.slice(2)) {
        const demander = clean(row[2]);
        if (!demander || ['示例', '无'].includes(demander)) continue;
        const seq = clean(row[0]), date = parseDate(row[1]) || today();
        const strain = normalizeStrain(store, row[3]), target_room = clean(row[5]);
        if (store.find('transfer_requests', item => item.seq === seq && item.demander === demander && item.request_date === date && item.strain === strain)) continue;
        const person = ensureClaimer(store, demander, target_room); result.claimers_imported++;
        const selected = row.slice(9, 20).flatMap(value => codes(value)).filter(code => !['已转', '取消', '无', '已完成'].includes(code) && validCode(code));
        const rowText = row.map(clean).join(' ');
        const status = rowText.includes('取消') ? '取消' : !selected.length && !rowText.includes('已转') ? '申请中' : '已转';
        const request = store.add('transfer_requests', { seq, request_date: date, demander, strain, age_gender_req: clean(row[4]) || '成年/无要求',
          target_room, cage_count: Number.parseInt(row[6]) || 1, source_room: clean(row[7]), mouse_gender: clean(row[8]),
          mouse_codes: selected.join(', '), status, feedback: clean(row[15]), handler: '系统导入' });
        result.transfer_requests_imported++;
        if (selected.length) {
          addLog(store, '系统导入', { action_type: '转鼠/领用', mouse_codes: request.mouse_codes, mouse_count: selected.length, claimer_name: demander,
            source_room: request.source_room, target_room, date, status, notes: `品系: ${strain}; 要求: ${request.age_gender_req}` });
          result.transfers_imported++;
          // Imported historical approvals have no original location snapshot; do not invent one.
          if (status === '已转') for (const code of selected) {
            const mouse = store.find('mice', item => item.mouse_code === code);
            if (mouse && !mouse.owner_id) { mouse.owner_id = person.id; mouse.owner_name = person.name; mouse.claim_date = date; mouse.status = mouse.cage_id ? '已领用' : '出笼'; }
          }
        }
      }
    } else if (kind === 6) {
      recognized++;
      for (const row of rows.slice(1)) {
        const strain_short = clean(row[1]), sequence = clean(row[7]);
        if ((!strain_short && !sequence) || store.find('primers', item => item.strain_short === strain_short && item.sequence === sequence)) continue;
        store.add('primers', { primer_no: Number.parseInt(row[0]) || null, strain_short, strain_full: clean(row[2]), source: clean(row[4]), gene_type: clean(row[5]), sequence, band_size: clean(row[8]), url: clean(row[9]) });
        result.primers_imported++;
      }
    }
  }
  if (!recognized) fail(400, '未识别到可导入的数据表，请保留实验室表名和表头');
  for (const [code, gender] of inferred) {
    const mouse = store.find('mice', item => item.mouse_code === code);
    if (mouse && (!mouse.gender || mouse.gender === '未知')) { mouse.gender = gender; result.inferred_genders_count++; }
  }
  for (const mouse of store.list('mice')) {
    applyOwnerStatus(store, mouse);
    if (!mouse.cage_id && ['在笼', '已领用', '繁育中'].includes(mouse.status)) mouse.status = '出笼';
    if (mouse.cage_id && ['出笼', '在笼'].includes(mouse.status)) mouse.status = mouse.owner_id || mouse.owner_name ? '已领用' : '在笼';
    ensureStatus(store, mouse.status || '出笼');
  }
  return result;
}

function checkZipSize(bytes) {
  if (bytes[0] !== 0x50 || bytes[1] !== 0x4b) return; // Legacy .xls is not a ZIP container.
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  let total = 0;
  for (let i = 0; i + 46 <= bytes.length; i++) if (view.getUint32(i, true) === 0x02014b50) {
    total += view.getUint32(i + 24, true);
    if (total > 64 * 1024 * 1024) fail(413, '解压后的 Excel 内容不能超过 64 MB');
    i += 45 + view.getUint16(i + 28, true) + view.getUint16(i + 30, true) + view.getUint16(i + 32, true);
  }
}
export async function uploadExcel(db, form) {
  const files = [...form.values()].filter(value => typeof value?.arrayBuffer === 'function');
  if (!files.length || files.length > 10) fail(400, '每次请选择 1–10 个 Excel 文件');
  const store = await Store.load(db), details = metrics(), summaries = [];
  for (const file of files) {
    const checkpoint = structuredClone(store.rows);
    try {
      if (!/\.xlsx?$/i.test(file.name)) fail(400, '仅支持 .xlsx 或 .xls 文件');
      const bytes = new Uint8Array(await file.arrayBuffer());
      checkZipSize(bytes);
      const workbook = read(bytes, { type: 'array', cellDates: true, cellFormula: false, cellHTML: false, cellStyles: false, sheetRows: 50002 });
      const result = importWorkbook(store, workbook);
      for (const key of Object.keys(details)) if (key !== 'errors') details[key] += result[key] || 0;
      const count = ['mice_imported', 'cages_imported', 'genotypes_imported', 'transfer_requests_imported', 'transfers_imported', 'primers_imported'].reduce((sum, key) => sum + result[key], 0);
      summaries.push({ filename: file.name, success: true, imported_count: count, details: result });
    } catch (error) {
      store.rows = checkpoint;
      const description = error.status ? error.message : 'Excel 文件损坏或格式不受支持';
      summaries.push({ filename: file.name, success: false, imported_count: 0, error: description });
      details.errors.push(`${file.name}: ${description}`);
    }
  }
  const successCount = summaries.filter(row => row.success).length;
  if (!successCount) fail(400, details.errors.join('；'));
  await store.commit(db);
  return { success: true, file_count: files.length, imported_count: summaries.reduce((sum, row) => sum + row.imported_count, 0),
    details, file_summaries: summaries, message: `已解析 ${files.length} 个文件，成功 ${successCount} 个，新增 ${details.mice_imported} 只小鼠、${details.genotypes_imported} 条基因鉴定` };
}

export async function exportExcel(db, resource) {
  if (!['mice', 'cages'].includes(resource)) fail(404, '导出类型未找到');
  const workbook = utils.book_new();
  if (resource === 'mice') {
    const rows = await all(db, 'SELECT m.*,c.room AS cage_room,c.cage_code FROM mice m LEFT JOIN cages c ON c.id=m.cage_id ORDER BY m.id DESC');
    const groups = new Map();
    for (const row of rows) { const room = clean(row.cage_room || row.source_room) || '未分配鼠房'; if (!groups.has(room)) groups.set(room, []); groups.get(room).push(row); }
    if (!groups.size) groups.set('未分配鼠房', []);
    for (const [room, mice] of groups) {
      const data = [['耳标编号', '品系/基因型', '性别', '出生日期', '周龄', '所在鼠房', '所在笼位', '领取人', '领用日期', '领用目的', 'Genotype 1', 'Genotype 2', '测试日期', '父母来源', '状态', '备注']];
      for (const mouse of mice) data.push([mouse.mouse_code, mouse.strain || '', mouse.gender || '', mouse.dob || '', '', room, mouse.cage_code || '', mouse.owner_name || '', mouse.claim_date || '', mouse.claim_purpose || '', mouse.genotype_1 || '', mouse.genotype_2 || '', mouse.test_date || '', mouse.parents || '', mouse.status || '', mouse.notes || '']);
      const sheet = utils.aoa_to_sheet(data);
      for (let r = 2; r <= data.length; r++) sheet[`E${r}`] = { t: 'n', f: `IF(D${r}="","",IFERROR(ROUND((TODAY()-IF(ISNUMBER(D${r}),D${r},DATEVALUE(D${r})))/7,1),""))` };
      sheet['!autofilter'] = { ref: sheet['!ref'] };
      let title = room.replace(/[\\/*?:\[\]\x00-\x1f]/g, '_').replace(/^'+|'+$/g, '').slice(0, 31) || '未分配鼠房';
      const base = title;
      for (let n = 2; workbook.SheetNames.some(name => name.toLowerCase() === title.toLowerCase()); n++) { const suffix = ` (${n})`; title = base.slice(0, 31 - suffix.length) + suffix; }
      utils.book_append_sheet(workbook, sheet, title);
    }
  } else {
    const result = await db.batch([db.prepare('SELECT * FROM cages ORDER BY room,cage_code'), db.prepare('SELECT mouse_code,cage_id FROM mice WHERE cage_id IS NOT NULL')]);
    const data = [['鼠房', '笼位号', '品系', '性别', '容量', '在笼数量', '在笼小鼠耳标', '合笼日期', '生鼠日期', '观察记录', '备注']];
    for (const cage of result[0].results) {
      const mouseCodes = result[1].results.filter(mouse => mouse.cage_id === cage.id).map(mouse => mouse.mouse_code);
      data.push([cage.room, cage.cage_code, cage.strain || '', cage.gender || '', cage.capacity, mouseCodes.length, mouseCodes.join(', '), cage.mating_date || '', litterDateText(cage), cage.observation || '', cage.notes || '']);
    }
    utils.book_append_sheet(workbook, utils.aoa_to_sheet(data), '小鼠笼位导出');
  }
  const bytes = write(workbook, { type: 'array', bookType: 'xlsx', compression: true });
  return new Response(bytes, { headers: { 'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'Content-Disposition': `attachment; filename="${resource}_export_${today().replaceAll('-', '')}.xlsx"`, 'Cache-Control': 'no-store' } });
}
