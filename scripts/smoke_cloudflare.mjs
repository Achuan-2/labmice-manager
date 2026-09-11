// Read-only deployment smoke checks. Exports a backup locally and compares every
// laboratory table with the prepared migration snapshot; credentials are never logged.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { DatabaseSync } from 'node:sqlite';
import assert from 'node:assert/strict';
import { schema } from '../cloudflare/schema.js';
import { resolve } from 'node:path';

const args = Object.fromEntries(process.argv.slice(2).map(value => { const index = value.indexOf('='); return [value.slice(0, index), value.slice(index + 1)]; }));
const base = args['--url'] || 'http://127.0.0.1:8787';
const directory = args['--data'] || 'migration-output/initial';
const credentials = readFileSync(resolve(directory, 'credentials.txt'), 'utf8');
const username = credentials.match(/账号：([^\r\n]+)/)?.[1];
const password = credentials.match(/密码：([^\r\n]+)/)?.[1];
if (!username || !password) throw new Error('凭据文件中没有生成的初始账号；请提供包含“账号：… / 密码：…”的本地凭据文件');
async function request(path, options = {}) {
  const start = performance.now();
  const response = await fetch(base + path, options);
  return { response, elapsed: Math.round(performance.now() - start) };
}
const unauth = await request('/api/mice'); assert.equal(unauth.response.status, 401);
const health = await request('/api/health'); assert.equal((await health.response.json()).status, 'ok');
const loggedIn = await request('/api/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password }) });
assert.equal(loggedIn.response.status, 200, 'Login failed');
const { access_token: token } = await loggedIn.response.json();
const headers = { Authorization: `Bearer ${token}` };
const manifest = JSON.parse(readFileSync(resolve(directory, 'manifest.json'), 'utf8'));
const results = [];
for (const path of ['/api/auth/me', '/api/mice?page=1&page_size=50', '/api/cages', '/api/cages/rooms?include_categories=true', '/api/members', '/api/transfer-requests', '/api/genotypes?page=1', '/api/mouse-statuses', '/api/strains', '/api/primers', '/api/transfers', '/api/stats/dashboard']) {
  const { response, elapsed } = await request(path, { headers });
  assert.equal(response.status, 200, path + ': ' + await response.clone().text().then(text => text.slice(0, 100)));
  const body = await response.json();
  if (path.startsWith('/api/mice?')) assert.equal(body.total, manifest.counts.mice);
  if (path.startsWith('/api/genotypes?')) assert.equal(body.total, manifest.counts.genotype_records);
  if (path === '/api/cages') assert.equal(body.length, manifest.counts.cages);
  results.push({ path, status: response.status, milliseconds: elapsed });
}
for (const path of ['/', '/mice']) {
  const { response } = await request(path);
  assert.equal(response.status, 200, 'SPA ' + path);
  assert.ok(response.headers.get('Content-Type').includes('text/html'));
}
const backupResponse = await request('/api/import-export/database/export', { headers });
assert.equal(backupResponse.response.status, 200, 'Database export failed: ' + await backupResponse.response.clone().text().then(text => text.slice(0, 100)));
const outputDir = resolve('migration-output/verification'); mkdirSync(outputDir, { recursive: true });
const backupPath = resolve(outputDir, 'cloudflare-export.db');
writeFileSync(backupPath, new Uint8Array(await backupResponse.response.arrayBuffer()));
const exported = new DatabaseSync(backupPath, { readOnly: true });
const source = new DatabaseSync(resolve(directory, 'sqlite-snapshot.db'), { readOnly: true });
const counts = {};
try {
  assert.equal(exported.prepare('PRAGMA integrity_check').get().integrity_check, 'ok');
  assert.equal(exported.prepare('PRAGMA foreign_key_check').all().length, 0);
  for (const [table, columns] of Object.entries(schema)) {
    const sql = `SELECT ${Object.keys(columns).map(key => `"${key}"`).join(',')} FROM "${table}" ORDER BY id`;
    const normalize = rows => rows.map(row => Object.fromEntries(Object.entries(row).map(([key, value]) => [key, columns[key].type === 'JSON' && typeof value === 'string' ? JSON.parse(value) : value])));
    const expected = normalize(source.prepare(sql).all()), actual = normalize(exported.prepare(sql).all());
    assert.deepEqual(actual, expected, 'Backup round-trip mismatch: ' + table);
    counts[table] = actual.length;
  }
} finally { exported.close(); source.close(); }
for (const resource of ['mice', 'cages']) {
  const { response } = await request(`/api/import-export/export/${resource}`, { headers });
  assert.equal(response.status, 200, 'Excel export failed');
  const bytes = new Uint8Array(await response.arrayBuffer()); assert.equal(bytes[0], 0x50);
  writeFileSync(resolve(outputDir, `${resource}.xlsx`), bytes);
}
const report = { base, passed: true, api_checks: results, roundtrip_counts: counts, backup: backupPath };
writeFileSync(resolve(outputDir, 'smoke-report.json'), JSON.stringify(report, null, 2));
console.log(JSON.stringify(report, null, 2));
