import Link from "next/link";
import { get } from "@/lib/api";
import type { CaseList } from "@/lib/types";
import { usd } from "@/lib/format";
import { VerdictChip } from "@/components/VerdictChip";

const muted = "text-zinc-500 dark:text-zinc-400";

// 15:00 stub: lists what waits on a manager. The Approve button (server action → POST /approve) lands at 20:00.
export default async function ApprovalsPage() {
  const { cases } = await get<CaseList>("/cases?awaiting_approval=true");
  return (
    <div className="space-y-4">
      <h1 className="font-semibold">{`Pending approvals (${cases.length})`}</h1>
      {cases.length === 0 ? (
        <p className={muted}>Nothing waiting for approval.</p>
      ) : (
        cases.map((c) => (
          <article key={c.case_id} className="space-y-2 rounded-lg border border-zinc-200 p-4 text-sm dark:border-zinc-800">
            <div className="flex items-center gap-3">
              <VerdictChip verdict={c.verdict} />
              <span className="font-mono">{c.employee_id}</span>
              {c.facts.amount && <span className="font-semibold">{usd(Number(c.facts.amount.value))}</span>}
            </div>
            <p>“{c.text}”</p>
            <ul className={muted}>
              {c.violations.map((v) => (
                <li key={v.rule}>{`${v.rule}: ${v.text}`}</li>
              ))}
            </ul>
            <Link href={`/cases/${c.case_id}`} className="underline">
              Open case
            </Link>
          </article>
        ))
      )}
    </div>
  );
}
