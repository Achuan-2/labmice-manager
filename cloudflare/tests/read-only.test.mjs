import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Store } from '../database.js';
import { enrichMouse } from '../domain.js';

test('indexed read-only enrichment preserves cage and genotype results', async () => {
  const rows = {
    cages: [{ id: 1, cage_code: 'A1', room: '江湾' }],
    mice: [{ id: 1, mouse_code: 'M1', cage_id: 1, dob: '2026-01-01', parents: 'P1' },
      { id: 2, mouse_code: 'M2', cage_id: null }],
    genotype_records: [{ id: 1, mouse_id: 1, mouse_code: 'M1', parents: null },
      { id: 2, mouse_id: null, mouse_code: 'M2', parents: 'P2' }],
  };
  const normal = new Store(rows);
  const indexed = new Store(rows, 0, { readOnly: true });
  for (const mouse of rows.mice) for (const history of [false, true]) {
    assert.deepEqual(enrichMouse(indexed, mouse, history), enrichMouse(normal, mouse, history));
  }
  assert.equal(indexed.original, null);
  await assert.rejects(indexed.commit(null), /read-only/);
});
