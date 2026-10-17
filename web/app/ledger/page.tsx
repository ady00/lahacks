import Link from "next/link";
import { get, post } from "@/lib/api";
import type { AuditSummary, LedgerOut } from "@/lib/types";
import { usd } from "@/lib/format";
import { VerdictChip } from "@/components/VerdictChip";

const muted = "text-zinc-500 dark:text-zinc-400";

export default async function LedgerPage() {
  const [{ transactions, total }, audit] = await Promise.all([
    get<LedgerOut>("/ledger"),
    post<AuditSummary>("/ledger/audit", { company: "demo" }),
  ]);
  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
        <h1 className="mb-2 font-semibold">
          Audit · {audit.n} transactions <span className={`text-sm font-normal ${muted}`}>({audit.elapsed_ms} ms)</span>
        </h1>
        <div className="flex gap-4 text-sm">
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
                <span className="font-bold">{r.rule}</span> — {r.text} — <span className={muted}>{r.count}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {transactions.length === 0 ? (
        <p className={muted}>No transactions loaded yet.</p>
      ) : (
        <table className="w-full text-sm">
          <thead className={`text-left ${muted}`}>
            <tr>
              {["Txn", "Vendor", "Memo", "Amount", "Timestamp", "QB category", "Coded account", "Verdict", "Rules"].map((h) => (
                <th key={h} className="py-1 pr-3 font-normal">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {transactions.map((t) => (
              <tr key={t.txn_id} className="border-t border-zinc-100 dark:border-zinc-800">
                <td className="py-1 pr-3 font-mono">
                  {t.case ? <Link href={`/cases/${t.case.case_id}`} className="underline">{t.txn_id}</Link> : t.txn_id}
                </td>
                <td className="py-1 pr-3">{t.vendor}</td>
                <td className={`py-1 pr-3 ${muted}`}>{t.memo}</td>
                <td className="py-1 pr-3">{usd(t.amount)}</td>
                <td className={`py-1 pr-3 ${muted}`}>{t.timestamp}</td>
                <td className="py-1 pr-3">{t.qb_category}</td>
                <td className="py-1 pr-3 font-mono">{t.coded_account}</td>
                <td className="py-1 pr-3"><VerdictChip verdict={t.verdict} /></td>
                <td className="py-1 font-mono">{t.violations.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className={`text-sm ${muted}`}>{`Showing ${transactions.length} of ${total}`}</p>
    </div>
  );
}
