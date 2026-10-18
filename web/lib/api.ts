import { connection } from "next/server";

// The only place the API is addressed. Server-side only: the browser never calls the API
// (the https dashboard → http Vultr hop would be blocked as mixed content).
export const API_URL = process.env.API_URL ?? "http://localhost:8000";

async function call<T>(method: "GET" | "POST" | "DELETE", path: string, body?: unknown, timeoutMs?: number): Promise<T> {
  await connection(); // every caller is request-time: never prerender a page against the API at build
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      cache: "no-store",
      headers: { "content-type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: timeoutMs ? AbortSignal.timeout(timeoutMs) : undefined,
    });
  } catch {
    throw new Error(`API unreachable at ${API_URL}`);
  }
  if (!res.ok) throw new Error(`${method} ${path} → ${res.status}: ${await res.text()}`);
  return res.json();
}

export const get = <T>(path: string, timeoutMs?: number) => call<T>("GET", path, undefined, timeoutMs);
export const post = <T>(path: string, body?: unknown) => call<T>("POST", path, body);
export const del = <T>(path: string) => call<T>("DELETE", path);

/** The API's own `detail` out of a thrown call error, for showing a person; the whole message otherwise. */
export const detail = (e: unknown) => {
  const m = e instanceof Error ? e.message : String(e);
  return /"detail":\s*"((?:[^"\\]|\\.)*)"/.exec(m)?.[1] ?? m;
};
