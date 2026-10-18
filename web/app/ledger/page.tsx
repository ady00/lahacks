import Link from "next/link";
import { get, post } from "@/lib/api";
import type { AuditSummary, LedgerOut } from "@/lib/types";
import { usd, when } from "@/lib/format";
import { VerdictChip } from "@/components/VerdictChip";
import { PageHeader } from "@/components/PageHeader";
import { card, h2, muted } from "@/lib/ui";

const HEAD = ["Transaction", "Vendor", "Memo", "Amount", "When", "QuickBooks category", "Coded account", "Verdict", "Rules broken"];

export default async function LedgerPage() {
  const [{ transactions, total }, audit] = await Promise.all([
    get<LedgerOut>("/ledger"),
    post<AuditSummary>("/ledger/audit", { company: "demo" }),
  ]);
  return (
    <div className="space-y-6">
      <PageHeader title="Ledger" text="Every posted transaction, checked against the same rules as a new purchase." />
      <section className={`${card} p-7`}>
        <h2 className={`mb-2 ${h2}`}>
          {`Audit of ${audit.n} ${audit.n === 1 ? "transaction" : "transactions"}`}{" "}
          <span className={`text-sm font-normal ${muted}`}>{`in ${audit.elapsed_ms} ms`}</span>
        </h2>
        <div className="flex flex-wrap gap-4 text-sm">
          {(["compliant", "violation", "undetermined"] as const).map((v) => (
            <span key={v} className="flex items-center gap-1.5">
              <VerdictChip verdict={v} /> {audit.by_verdict[v] ?? 0}
            </span>
          ))}
        </div>
        {audit.by_rule.length > 0 && (
          <ul className="mt-3 text-sm">
            {audit.by_rule.map((r) => (
              <li key={r.rule}>
                <span className="font-mono text-xs font-semibold">{`Rule ${r.rule}`}</span> {r.text}{" "}
                <span className={muted}>{`· broken ${r.count} ${r.count === 1 ? "time" : "times"}`}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {transactions.length === 0 ? (
        <p className={muted}>No transactions loaded yet. They appear once the data files are loaded into the API.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className={`${card} w-full text-sm`}>
          <thead className={`text-left ${muted}`}>
            <tr>
              {HEAD.map((h) => (
                <th key={h} className="px-3 py-2 font-normal first:pl-5">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {transactions.map((t) => (
              <tr key={t.txn_id} className="border-t border-[#F1F5F9]">
                <td className="px-3 py-2 first:pl-5 font-mono text-xs">
                  {t.case ? <Link href={`/cases/${t.case.case_id}`} className="underline">{t.txn_id}</Link> : t.txn_id}
                </td>
                <td className="px-3 py-2 first:pl-5">{t.vendor}</td>
                <td className={`px-3 py-2 first:pl-5 ${muted}`}>{t.memo}</td>
                <td className="px-3 py-2 first:pl-5 whitespace-nowrap tabular-nums">{usd(t.amount)}</td>
                <td className={`px-3 py-2 first:pl-5 whitespace-nowrap ${muted}`}>{when(t.timestamp)}</td>
                <td className="px-3 py-2 first:pl-5">{t.qb_category}</td>
                <td className="px-3 py-2 first:pl-5 font-mono text-xs">{t.coded_account}</td>
                <td className="px-3 py-2 first:pl-5"><VerdictChip verdict={t.verdict} /></td>
                <td className="px-3 py-2 font-mono text-xs">{t.violations.length ? t.violations.join(", ") : <span className={muted}>none</span>}</td>
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
