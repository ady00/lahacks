import { get } from "@/lib/api";
import { requireUser } from "@/lib/session";
import type { Case } from "@/lib/types";
import { CaseCard } from "@/components/CaseCard";
import { PurchaseGraph } from "@/components/PurchaseGraph";
import type { CaseGraph } from "@/lib/graph";
import { headline, usd } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { btn, btnPrimary, input } from "@/lib/ui";

// the numeric questions the engine can ask (api/explain.py); every other question is yes/no or an enum
const NUMERIC = new Set(["amount", "attendees", "nights", "days", "days_before_travel"]);

// Every button is a native form to /act/<verb>; the API re-proves and this page re-renders whatever it says.
export default async function CasePage({ params }: PageProps<"/cases/[id]">) {
  await requireUser();
  const { id } = await params;
  const c = await get<Case>(`/cases/${id}`);
  const graph = await get<CaseGraph>(`/cases/${id}/graph`, 12000).catch(() => null);
  const q = c.questions[0];
  const choices = q ? (q.options ?? ["true", "false"]) : [];
  const { title, next } = headline(c);
  const amount = c.facts.amount?.value;
  const numeric = q && NUMERIC.has(q.fact);
  return (
    <div className="animate-fade-in-up space-y-6">
      <PageHeader title={title} text={next}>
        {/* eslint-disable-next-line @next/next/no-html-link-for-pages -- plain anchors on purpose: the refresh timer must never pull users back */}
        <a href="/" className={btn}>Check another purchase</a>
      </PageHeader>
      <PurchaseGraph key={graph?.base_facts_hash ?? JSON.stringify(c.facts)} initialGraph={graph} awaitingApproval={c.awaiting_approval}>
      {q && numeric ? (
        <form method="post" action="/act/answer" className="animate-fade-in flex flex-wrap items-end gap-3 rounded-xl border border-amber-200 bg-amber-50/70 p-5 shadow-xs">
          <input type="hidden" name="case_id" value={c.case_id} />
          <input type="hidden" name="fact" value={q.fact} />
          <label className="text-sm font-medium text-amber-950">
            {q.text}
            <input name="value" type="number" step={q.fact === "amount" ? "0.01" : "1"} min={q.fact === "amount" ? "0.01" : q.fact === "days_before_travel" ? "0" : "1"} required className={`${input} mt-1.5`} />
          </label>
          <button className={btnPrimary}>Submit Answer</button>
        </form>
      ) : q && (
        <section className="animate-fade-in rounded-xl border border-amber-200 bg-amber-50/70 p-5 shadow-xs space-y-3">
          <div className="flex items-center gap-2 text-amber-800">
            <span className="relative flex size-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75" />
              <span className="relative inline-flex size-2 rounded-full bg-amber-500" />
            </span>
            <span className="text-xs font-bold uppercase tracking-wider">Required Detail</span>
          </div>
          <h2 className="font-serif text-[17px] font-bold tracking-tight text-amber-950">{q.text}</h2>
          <div className="flex flex-wrap gap-2.5 pt-1">
            {choices.map((v) => (
              <form key={v} method="post" action="/act/answer">
                <input type="hidden" name="case_id" value={c.case_id} />
                <input type="hidden" name="fact" value={q.fact} />
                <input type="hidden" name="value" value={v} />
                <button className={`${btn} font-semibold transition-all hover:border-secondary hover:text-secondary hover:shadow-xs active:scale-95`}>{q.options ? v : v === "true" ? "Yes" : "No"}</button>
              </form>
            ))}
          </div>
        </section>
      )}

      {c.verdict === "compliant" && !c.authorization && amount != null && (
        <form method="post" action="/act/authorize" className="animate-fade-in">
          <input type="hidden" name="case_id" value={c.case_id} />
          <button className={`${btnPrimary} px-6 py-2.5 text-[14px] shadow-[0_4px_16px_rgba(145,73,196,0.35)] hover:shadow-[0_6px_22px_rgba(145,73,196,0.45)]`}>
            💳 {`Authorize card for ${usd(Number(amount))}`}
          </button>
        </form>
      )}

      <CaseCard c={c} />
      </PurchaseGraph>
    </div>
  );
}
