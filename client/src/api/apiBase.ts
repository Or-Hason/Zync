/**
 * Origin that every backend call is prefixed with.
 *
 * Vite substitutes `import.meta.env.VITE_API_BASE` at build time:
 *
 * - **Dev** (`npm run dev`): the variable is unset, so this resolves to `""`
 *   and every request stays relative (`/api/...`). The Vite dev server proxies
 *   those to the backend, which keeps requests same-origin — no CORS involved.
 * - **Production** (`npm run build`, i.e. the packaged Tauri app): the value
 *   comes from `.env.production`. There is no Vite proxy inside the bundled
 *   WebView — relative paths would resolve against the `tauri://localhost`
 *   scheme instead of the backend port — so the absolute origin is required.
 *
 * Declared once here rather than inlined per module: the value must be
 * identical everywhere, and a compile-time constant cannot be re-read later.
 */
export const API_BASE = import.meta.env.VITE_API_BASE ?? "";
