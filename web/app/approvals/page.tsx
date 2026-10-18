import { get } from "@/lib/api";
import { requireUser } from "@/lib/session";
import type { CaseList } from "@/lib/types";
import { usd } from "@/lib/format";
import { VerdictChip } from "@/components/VerdictChip";
import { btn, btnPrimary, card, h1, muted } from "@/lib/ui";

// The manager's laptop: reloads itself every 5 s so a case checked elsewhere shows up without a click.
export default async function ApprovalsPage() {
  const user = await requireUser();
  if (!user.manager) {
    return (
      <p>
        Managers only — <a href="/login" className="underline">sign in as a manager</a>.
      </p>
    );
  }
  const { cases } = await get<CaseList>("/cases?awaiting_approval=true");
  return (
    <div className="space-y-4">
      <meta httpEquiv="refresh" content="5" />
      <h1 className={h1}>{`Pending approvals (${cases.length})`}</h1>
      {cases.length === 0 ? (
        <p className={muted}>Nothing waiting for approval.</p>
      ) : (
        cases.map((c) => (
          <article key={c.case_id} className={`${card} space-y-2 text-sm`}>
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
              <a href={`/cases/${c.case_id}`} className="ml-2 underline">
                Open case
              </a>
            </div>
          </article>
        ))
      )}
    </div>
  );
}
