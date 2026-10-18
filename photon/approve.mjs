// Manager approval by text (Photon Spectrum, iMessage). A sidecar beside the API: it polls
// GET /cases?awaiting_approval=true, texts the manager each new case once, and turns the
// reply into POST /cases/{id}/approve. The dashboard case page already reloads while a case
// waits, so the new hire sees the flip with no web changes.
//
// Env: SPECTRUM_PROJECT_ID, SPECTRUM_PROJECT_SECRET (app.photon.codes → project Settings),
//      MANAGER_PHONE (E.164, e.g. +13105551234), optional API_URL, MANAGER_ID (default e_manager).
import { Spectrum } from "spectrum-ts";
import { imessage } from "spectrum-ts/providers/imessage";
import { parseReply } from "./reply.mjs";

const API_URL = process.env.API_URL ?? "http://localhost:8000";
const MANAGER_ID = process.env.MANAGER_ID ?? "e_manager";
const MANAGER_PHONE = process.env.MANAGER_PHONE;
const POLL_MS = 3000; // ponytail: polling; have the API call out when latency matters
if (!MANAGER_PHONE) throw new Error("set MANAGER_PHONE (E.164, e.g. +13105551234)");

const api = async (method, path, body) => {
  const res = await fetch(API_URL + path, {
    method, headers: { "content-type": "application/json" }, body: body && JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${method} ${path} → ${res.status}: ${await res.text()}`);
  return res.json();
};

const app = await Spectrum({ providers: [imessage.config()] }); // credentials from SPECTRUM_* env
const im = imessage(app);
const manager = await im.user(MANAGER_PHONE);
const dm = await im.space.create(manager);
console.log(`texting ${MANAGER_PHONE} (space ${dm.id}) about cases from ${API_URL}`);

const money = (f) => (f ? `$${Number(f.value).toLocaleString("en-US", { maximumFractionDigits: 2 })}` : "an unknown amount");
let waiting = []; // case ids texted and still undecided, oldest first

async function poll() {
  const { cases } = await api("GET", "/cases?awaiting_approval=true");
  for (const c of cases) {
    if (waiting.includes(c.case_id)) continue;
    waiting.push(c.case_id);
    const hint = waiting.length > 1 ? ` with the case id` : "";
    await dm.send(`Approval needed (${c.case_id}): ${c.employee_id} wants to spend ${money(c.facts.amount)} — "${c.text}"\n` +
      `${c.explanation}\nReply YES or NO${hint}.`);
    console.log(`texted ${c.case_id}`);
  }
  const still = new Set(cases.map((c) => c.case_id));
  waiting = waiting.filter((id) => still.has(id)); // decided on the dashboard → drop it here too
}

await poll();
setInterval(() => poll().catch((e) => console.error("poll:", e.message)), POLL_MS);

for await (const [space, message] of app.messages) {
  if (message.direction !== "inbound" || message.content.type !== "text") continue;
  if (space.id !== dm.id && message.sender?.id !== manager.id) { // only the manager's line may approve
    console.warn(`ignoring text from space ${space.id} sender ${message.sender?.id}`);
    continue;
  }
  const r = parseReply(message.content.text, waiting);
  if (!r) { await space.send("Reply YES or NO (add the case id if more than one is waiting)."); continue; }
  if ("error" in r) { await space.send(r.error); continue; }
  try {
    const c = await api("POST", `/cases/${r.caseId}/approve`, { approver: MANAGER_ID, approved: r.approved });
    waiting = waiting.filter((id) => id !== r.caseId);
    await space.send(`${r.approved ? "Approved" : "Rejected"} ${r.caseId}. Verdict is now ${c.verdict}.`);
  } catch (e) {
    await space.send(`Could not record that: ${e.message}`);
  }
}
