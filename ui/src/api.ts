/** Resolve backend URL for API calls. Local dev: Vite proxies `/api` → FastAPI. */
export function apiUrl(path: string): string {
  const base = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "";
  const p = path.startsWith("/") ? path : `/${path}`;
  if (base) {
    return `${base}${p}`;
  }
  return `/api${p}`;
}
