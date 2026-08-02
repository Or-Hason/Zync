/// <reference types="vite/client" />

/**
 * Typed build-time environment. `vite/client` only declares an `any` index
 * signature, which would silently accept a typo in a variable name.
 */
interface ImportMetaEnv {
  /**
   * Absolute origin of the FastAPI backend, injected at build time.
   * Undefined in dev, where relative paths go through the Vite proxy instead.
   */
  readonly VITE_API_BASE?: string;
}

declare module "*.module.css" {
  const classes: Record<string, string>;
  export default classes;
}
