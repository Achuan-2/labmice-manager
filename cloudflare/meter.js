// Per-request counters; never persist monitoring data back into D1.
export function meterDatabase(db) {
  const usage = { rows_read: 0, rows_written: 0, queries: 0 };
  const originals = new WeakMap();
  const count = result => {
    usage.queries++;
    usage.rows_read += result.meta?.rows_read || 0;
    usage.rows_written += result.meta?.rows_written || 0;
    return result;
  };
  function wrap(statement) {
    const wrapped = {
      bind: (...values) => wrap(statement.bind(...values)),
      all: async () => count(await statement.all()),
      run: async () => count(await statement.run()),
      first: async column => {
        const row = (await wrapped.all()).results[0];
        return row ? column === undefined ? row : row[column] : null;
      },
    };
    originals.set(wrapped, statement);
    return wrapped;
  }
  return { usage, db: {
    prepare: sql => wrap(db.prepare(sql)),
    batch: async statements => (await db.batch(statements.map(s => originals.get(s) || s))).map(count),
  } };
}
