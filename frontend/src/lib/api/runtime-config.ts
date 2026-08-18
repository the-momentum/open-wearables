const FALLBACK_API_URL = 'http://localhost:8000';

declare global {
  interface Window {
    __APP_CONFIG__?: { apiUrl?: string };
  }
}

/**
 * Resolve the backend API base URL from a single env var: VITE_API_URL.
 *
 * The same name works both at build time (Vite inlines import.meta.env) and at
 * runtime (the container's VITE_API_URL env var), so a prebuilt image can point
 * at any backend (e.g. https://api.client1.com) without rebuilding. Order of
 * precedence:
 *
 *   1. Browser: window.__APP_CONFIG__.apiUrl, injected into the SSR HTML from
 *      the container's VITE_API_URL env var (see routes/__root.tsx).
 *   2. SSR server (Nitro runtime): process.env.VITE_API_URL.
 *   3. VITE_API_URL baked at build time (dev / opt-in build-time config).
 *   4. http://localhost:8000.
 */
export function resolveApiUrl(): string {
  if (typeof window !== 'undefined') {
    return (
      window.__APP_CONFIG__?.apiUrl ||
      import.meta.env.VITE_API_URL ||
      FALLBACK_API_URL
    );
  }

  const env = typeof process !== 'undefined' ? process.env : undefined;
  return env?.VITE_API_URL || import.meta.env.VITE_API_URL || FALLBACK_API_URL;
}

/**
 * Inline script that publishes the runtime config to the browser before the
 * app bundle hydrates. Rendered into the SSR document head/body.
 */
export function runtimeConfigScript(): string {
  const config = { apiUrl: resolveApiUrl() };
  // JSON.stringify + escape `<` so the value can't break out of the <script>.
  return `window.__APP_CONFIG__ = ${JSON.stringify(config).replace(/</g, '\\u003c')};`;
}
