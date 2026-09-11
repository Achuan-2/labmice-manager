// Set the tiny compatibility value before the Worker graph imports sql.js.
// A static import evaluates its dependencies first, so use a top-level import
// after the polyfill instead.
if (typeof globalThis.self !== 'undefined' && !globalThis.self.location) {
  globalThis.self.location = { href: 'https://worker.invalid/' };
}
const { default: app } = await import('./worker.js');
export default app;
