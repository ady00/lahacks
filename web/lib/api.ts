import { connection } from "next/server";

// The only place the API is addressed. Server-side only: the browser never calls the API
// (the https dashboard → http Vultr hop would be blocked as mixed content).
export const API_URL = process.env.API_URL ?? "http://localhost:8000";

async function call<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
  await connection(); // every caller is request-time: never prerender a page against the API at build
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      cache: "no-store",
      headers: { "content-type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new Error(`API unreachable at ${API_URL}`);
  }
  if (!res.ok) throw new Error(`${method} ${path} → ${res.status}: ${await res.text()}`);
  return res.json();
}

export const get = <T>(path: string) => call<T>("GET", path);
export const post = <T>(path: string, body?: unknown) => call<T>("POST", path, body);
