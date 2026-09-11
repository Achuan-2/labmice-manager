import { test } from 'node:test';
import assert from 'node:assert/strict';
import { TestDatabase } from './sqlite-adapter.mjs';
import { Store } from '../database.js';

test('notes edit does not touch indexed columns and an unchanged commit writes nothing', async () => {
  const db = new TestDatabase();
  try {
    const seed = await Store.load(db);
    seed.add('mice', { mouse_code: 'COST1', strain: 'C57', notes: 'before' });
    await seed.commit(db);
    db.sqlite.exec(`CREATE TRIGGER reject_index_update BEFORE UPDATE OF mouse_code,strain,cage_id,owner_id ON mice BEGIN SELECT RAISE(ABORT,'unrelated index touched'); END;`);
    const store = await Store.load(db);
    store.rows.mice[0].notes = 'after';
    await store.commit(db);
    assert.equal(db.sqlite.prepare('SELECT notes FROM mice').get().notes, 'after');
    const unchanged = await Store.load(db);
    const before = db.sqlite.prepare('SELECT total_changes() AS n').get().n;
    await unchanged.commit(db);
    assert.equal(db.sqlite.prepare('SELECT total_changes() AS n').get().n, before);
  } finally { db.close(); }
});
