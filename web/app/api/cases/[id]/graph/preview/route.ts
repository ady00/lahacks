import { API_URL } from "@/lib/api";
import { getUser } from "@/lib/session";

export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  if (!await getUser()) return Response.json({ detail: "Sign in required" }, { status: 401 });
  const { id } = await params;
  let body: unknown;
  try { body = await request.json(); }
  catch { return Response.json({ detail: "Invalid JSON" }, { status: 400 }); }
  try {
    const result = await fetch(`${API_URL}/cases/${encodeURIComponent(id)}/graph/preview`, {
      method: "POST", headers: { "content-type": "application/json" }, cache: "no-store",
      body: JSON.stringify(body), signal: AbortSignal.timeout(12000),
    });
    return Response.json(await result.json(), { status: result.status, headers: { "cache-control": "no-store" } });
  } catch {
    return Response.json({ detail: "Preview analysis unavailable" }, { status: 503 });
  }
}
