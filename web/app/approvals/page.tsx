import Link from "next/link";
import { get } from "@/lib/api";
import { requireUser } from "@/lib/session";
import type { CaseList } from "@/lib/types";
import { usd } from "@/lib/format";
import { VerdictChip } from "@/components/VerdictChip";

const muted = "text-zinc-500 dark:text-zinc-400";
const btn = "rounded border border-zinc-300 px-3 py-1.5 text-sm hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800";
const btnPrimary = "rounded bg-zinc-900 px-4 py-2 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900";

// The manager's laptop: reloads itself every 5 s so a case checked elsewhere shows up without a click.
export default async function ApprovalsPage() {
  const user = await requireUser();
  if (!user.manager) {
    return (
      <p>
        Managers only — <Link href="/login" className="underline">sign in as a manager</Link>.
      </p>
    );
  }
  const { cases } = await get<CaseList>("/cases?awaiting_approval=true");
  return (
    <div className="space-y-4">
      <meta httpEquiv="refresh" content="5" />
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
            <div className="flex items-center gap-2">
              <form method="post" action="/act/approve">
                <input type="hidden" name="case_id" value={c.case_id} />
                <input type="hidden" name="approved" value="true" />
                <button className={btnPrimary}>Approve</button>
              </form>
              <form method="post" action="/act/approve">
                <input type="hidden" name="case_id" value={c.case_id} />
                <input type="hidden" name="approved" value="false" />
                <button className={btn}>Reject</button>
              </form>
              <Link href={`/cases/${c.case_id}`} className="ml-2 underline">
                Open case
              </Link>
            </div>
          </article>
        ))
      )}
    </div>
  );
}
