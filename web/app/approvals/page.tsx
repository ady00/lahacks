import { get } from "@/lib/api";
import { requireUser } from "@/lib/session";
import type { CaseList, EmployeeList } from "@/lib/types";
import { usd, when } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { btn, btnPrimary, h1, muted, row } from "@/lib/ui";

// The manager's laptop: reloads itself every 5 s so a case checked elsewhere shows up without a click.
export default async function ApprovalsPage() {
  const user = await requireUser();
  if (!user.manager) {
    return (
      <div className="space-y-2">
        <h1 className={h1}>Approvals are for managers</h1>
        <p className="text-sm">
          <a href="/login" className="underline">Sign in again</a> and tick “I approve purchases” to see this page.
        </p>
      </div>
    );
  }
  const [{ cases }, { employees }] = await Promise.all([get<CaseList>("/cases?awaiting_approval=true"), get<EmployeeList>("/employees")]);
  const names = new Map(employees.map((e) => [e.employee_id, e.name]));
  return (
    <div className="space-y-4">
      <meta httpEquiv="refresh" content="5" />
      <PageHeader
        title={cases.length === 1 ? "1 purchase waiting for your approval" : `${cases.length} purchases waiting for your approval`}
        text="Approve or reject. The rules re-check and the requester's page updates on its own."
      />
      {cases.length === 0 ? (
        <p className={muted}>Nothing is waiting. New requests appear here within a few seconds.</p>
      ) : (
        cases.map((c) => (
          <article key={c.case_id} className={`${row} space-y-3 text-sm`}>
            <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              {c.facts.amount && <span className="text-lg font-semibold">{usd(Number(c.facts.amount.value))}</span>}
              <span className="font-medium">{names.get(c.employee_id) || c.employee_id}</span>
              <span className={muted}>{`asked ${when(c.created_at)}`}</span>
            </div>
            <p className="text-base">“{c.text}”</p>
            <ul className={muted}>
              {c.violations.map((v) => (
                <li key={v.rule}>{`Rule ${v.rule}: ${v.text}`}</li>
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
                See the full check
              </a>
            </div>
          </article>
        ))
      )}
    </div>
  );
}
