import { get } from "@/lib/api";
import { requireUser } from "@/lib/session";
import type { Case } from "@/lib/types";
import { CaseCard } from "@/components/CaseCard";
import { btn, btnPrimary, h1, input } from "@/lib/ui";

// Every button is a native form to /act/<verb>; the API re-proves and this page re-renders whatever it says.
export default async function CasePage({ params }: PageProps<"/cases/[id]">) {
  await requireUser();
  const { id } = await params;
  const c = await get<Case>(`/cases/${id}`);
  const q = c.questions[0];
  const choices = q ? (q.options ?? ["true", "false"]) : [];
  return (
    <div className="space-y-6">
      {c.awaiting_approval && <meta httpEquiv="refresh" content="5" />}
      <h1 className={h1}>{`Case ${c.case_id}`}</h1>
      <CaseCard c={c} />

      {q && q.fact === "amount" ? (
        // the one numeric question the engine asks (api/explain.py); every other question is yes/no or an enum
        <form method="post" action="/act/answer" className="flex items-end gap-2">
          <input type="hidden" name="case_id" value={c.case_id} />
          <input type="hidden" name="fact" value="amount" />
          <label className="text-sm">
            {q.text}
            <input name="value" type="number" step="0.01" min="0.01" required className={input} />
          </label>
          <button className={btnPrimary}>Submit</button>
        </form>
      ) : q && (
        <section className="space-y-2">
          <h2 className="font-semibold">{q.text}</h2>
          <div className="flex flex-wrap gap-2">
            {choices.map((v) => (
              <form key={v} method="post" action="/act/answer">
                <input type="hidden" name="case_id" value={c.case_id} />
                <input type="hidden" name="fact" value={q.fact} />
                <input type="hidden" name="value" value={v} />
                <button className={btn}>{q.options ? v : v === "true" ? "Yes" : "No"}</button>
              </form>
            ))}
          </div>
        </section>
      )}

      {c.verdict === "compliant" && !c.authorization && (
        <form method="post" action="/act/authorize">
          <input type="hidden" name="case_id" value={c.case_id} />
          <button className={btnPrimary}>Authorize card</button>
        </form>
      )}
    </div>
  );
}
