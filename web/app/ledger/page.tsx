import Link from "next/link";
import { get, post } from "@/lib/api";
import { DECIMAL, NUMERIC, type AuditSummary, type LedgerOut, type LedgerRow } from "@/lib/types";
import { usd, when } from "@/lib/format";
import { VerdictChip } from "@/components/VerdictChip";
import { PageHeader } from "@/components/PageHeader";
import { btnPrimary, card, h2, muted } from "@/lib/ui";

const HEAD = ["Transaction", "Vendor", "Memo", "Amount", "When", "QuickBooks category", "Coded account", "Verdict", "Rules broken"];

const field = "rounded-md border border-main bg-white px-2 py-1 text-xs text-ink focus:border-secondary focus:outline-none";

// "Needs a detail" opens to the engine's next question; answering re-decides just this row (POST /ledger/{id}/answer).
function Verdict({ t }: { t: LedgerRow }) {
  const q = t.verdict === "undetermined" ? t.case?.questions[0] : undefined;
  if (!q) return <VerdictChip verdict={t.verdict} />;
  const numeric = NUMERIC.has(q.fact);
  return (
    <details className="group">
      <summary className="cursor-pointer list-none [&::-webkit-details-marker]:hidden">
        <VerdictChip verdict={t.verdict} />
        <span className="ml-1 inline-block text-[10px] text-[#D97706] transition-transform group-open:rotate-180">▾</span>
      </summary>
      <form method="post" action="/act/ledger-answer" className="mt-2 w-56 space-y-2 rounded-md border border-amber-200 bg-amber-50/70 p-2.5">
        <input type="hidden" name="txn_id" value={t.txn_id} />
        <input type="hidden" name="fact" value={q.fact} />
        <label className="block text-xs font-medium text-amber-950">
          {q.text}
          {numeric ? (
            <input name="value" type="number" required step={DECIMAL.has(q.fact) ? "0.01" : "1"} min="0" className={`${field} mt-1.5 w-full`} />
          ) : (
            <select name="value" required defaultValue="" className={`${field} mt-1.5 w-full`}>
              <option value="" disabled>Choose…</option>
              {(q.options ?? ["true", "false"]).map((v) => (
                <option key={v} value={v}>{q.options ? v : v === "true" ? "Yes" : "No"}</option>
              ))}
            </select>
          )}
        </label>
        <button className={`${btnPrimary} px-3 py-1 text-xs`}>Save</button>
      </form>
    </details>
  );
}

export default async function LedgerPage() {
  const [{ transactions, total }, audit] = await Promise.all([
    get<LedgerOut>("/ledger"),
    post<AuditSummary>("/ledger/audit", { company: "demo" }),
  ]);
  return (
    <div className="animate-fade-in-up space-y-6">
      <PageHeader title="Ledger" text="Every posted transaction, newest first, checked against the same rules as a new purchase." />
      <section className={`${card} p-7 hover:shadow-[0_14px_30px_-6px_rgba(15,23,42,0.08)]`}>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h2 className={h2}>
            {`Audit of ${audit.n} ${audit.n === 1 ? "transaction" : "transactions"}`}{" "}
            <span className={`text-sm font-normal ${muted}`}>{`in ${audit.elapsed_ms} ms`}</span>
          </h2>
          <div className="flex flex-wrap gap-4 text-sm">
            {(["compliant", "violation", "undetermined"] as const).map((v) => (
              <span key={v} className="flex items-center gap-1.5 font-medium">
                <VerdictChip verdict={v} /> {audit.by_verdict[v] ?? 0}
              </span>
            ))}
          </div>
        </div>
        {audit.by_rule.length > 0 && (
          <ul className="mt-4 space-y-1.5 border-t border-[#F1F5F9] pt-3 text-sm">
            {audit.by_rule.map((r) => (
              <li key={r.rule} className="flex items-baseline gap-2">
                <span className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs font-semibold text-slate-800">{`Rule ${r.rule}`}</span>
                <span>{r.text}</span>
                <span className={muted}>{`· broken ${r.count} ${r.count === 1 ? "time" : "times"}`}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {transactions.length === 0 ? (
        <p className={muted}>No transactions loaded yet. They appear once the data files are loaded into the API.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-[#F1F5F9]">
          <table className={`${card} w-full text-sm`}>
          <thead className={`bg-[#F8FAFC] text-left ${muted}`}>
            <tr>
              {HEAD.map((h) => (
                <th key={h} className="px-3.5 py-2.5 font-medium first:pl-5">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {transactions.map((t) => (
              <tr key={t.txn_id} className="border-t border-[#F1F5F9] transition-colors duration-150 hover:bg-[#F8FAFC]">
                <td className="px-3.5 py-2.5 first:pl-5 font-mono text-xs">
                  {t.case ? <Link href={`/cases/${t.case.case_id}`} className="font-semibold text-secondary hover:underline transition-colors">{t.txn_id}</Link> : t.txn_id}
                </td>
                <td className="px-3.5 py-2.5 font-medium text-zinc-900">{t.vendor}</td>
                <td className={`px-3.5 py-2.5 ${muted}`}>{t.memo}</td>
                <td className="px-3.5 py-2.5 whitespace-nowrap tabular-nums font-semibold text-zinc-900">{usd(t.amount)}</td>
                <td className={`px-3.5 py-2.5 whitespace-nowrap ${muted}`}>{when(t.timestamp)}</td>
                <td className="px-3.5 py-2.5">{t.qb_category}</td>
                <td className="px-3.5 py-2.5 font-mono text-xs">{t.coded_account}</td>
                <td className="px-3.5 py-2.5 align-top"><Verdict t={t} /></td>
                <td className="px-3.5 py-2.5 font-mono text-xs">{t.violations.length ? t.violations.join(", ") : <span className={muted}>none</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      )}
      <p className={`text-sm ${muted}`}>{`Showing ${transactions.length} of ${total}`}</p>
    </div>
  );
}
