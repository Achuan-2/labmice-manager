import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';

// Executes real SQLite SQL (including json_each, foreign keys and triggers), with
// the same atomic batch contract as D1. It never touches the laboratory database.
export class TestDatabase {
  constructor() {
    this.sqlite = new DatabaseSync(':memory:');
    this.sqlite.exec('PRAGMA foreign_keys=ON');
    for (const name of ['0001_initial.sql', '0002_operational.sql', '0003_todo_reminders.sql', '0004_litter_birth_batches.sql', '0005_todo_multiple_relations.sql', '0006_euthanasia_owner.sql', '0007_system_settings.sql']) this.sqlite.exec(readFileSync(new URL(`../migrations/${name}`, import.meta.url), 'utf8'));
  }
  prepare(sql) {
    const db = this.sqlite;
    const build = params => ({
      bind: (...values) => build(values),
      all: async () => ({ success: true, results: db.prepare(sql).all(...params) }),
      first: async () => db.prepare(sql).get(...params) || null,
      run: async () => ({ success: true, meta: db.prepare(sql).run(...params) }),
    });
    return build([]);
  }
  async batch(statements) {
    this.sqlite.exec('BEGIN');
    try {
      const result = [];
      for (const statement of statements) result.push(await statement.all());
      this.sqlite.exec('COMMIT');
      return result;
    } catch (error) {
      this.sqlite.exec('ROLLBACK'); throw error;
    }
  }
  close() { this.sqlite.close(); }
}
