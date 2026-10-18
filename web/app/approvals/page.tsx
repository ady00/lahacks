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
    <div className="animate-fade-in-up space-y-4">
      <meta httpEquiv="refresh" content="5" />
      <PageHeader
        title={cases.length === 1 ? "1 purchase waiting for your approval" : `${cases.length} purchases waiting for your approval`}
        text="Approve or reject. The rules re-check and the requester's page updates on its own."
      >
        <span className="flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 shadow-2xs">
          <span className="relative flex size-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />
            <span className="relative inline-flex size-2 rounded-full bg-blue-600" />
          </span>
          <span className="font-serif text-[11.5px] font-semibold text-ink">Live refresh (5s)</span>
        </span>
      </PageHeader>
      {cases.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-200 bg-white/50 p-12 text-center">
          <p className="font-medium text-slate-700">All clear — no pending approvals</p>
          <p className={`mt-1 text-xs ${muted}`}>New purchase requests will automatically stream in here.</p>
        </div>
      ) : (
        cases.map((c) => (
          <article key={c.case_id} className={`${row} space-y-3.5 text-sm transition-all duration-200 hover:border-slate-300 hover:shadow-md`}>
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
              <div className="flex items-baseline gap-3">
                {c.facts.amount && <span className="text-xl font-bold tracking-tight text-ink">{usd(Number(c.facts.amount.value))}</span>}
                <span className="font-semibold text-slate-800">{names.get(c.employee_id) || c.employee_id}</span>
                <span className={`text-xs ${muted}`}>{`asked ${when(c.created_at)}`}</span>
              </div>
              <span className="font-mono text-xs text-slate-400">{c.case_id}</span>
            </div>
            <p className="rounded-lg border border-slate-100 bg-[#F8FAFC] p-3 text-base font-medium text-slate-900">“{c.text}”</p>
            <ul className="space-y-1 text-xs text-red-600">
              {c.violations.map((v) => (
                <li key={v.rule} className="flex items-center gap-1.5">
                  <span className="font-mono font-semibold">{`Rule ${v.rule}:`}</span>
                  <span>{v.text}</span>
                </li>
              ))}
            </ul>
            <div className="flex items-center gap-3 pt-1">
              <form method="post" action="/act/approve">
                <input type="hidden" name="case_id" value={c.case_id} />
                <input type="hidden" name="approved" value="true" />
                <button className={btnPrimary}>✓ Approve</button>
              </form>
              <form method="post" action="/act/approve">
                <input type="hidden" name="case_id" value={c.case_id} />
                <input type="hidden" name="approved" value="false" />
                <button className={btn}>✕ Reject</button>
              </form>
              <a href={`/cases/${c.case_id}`} className="ml-2 font-serif text-[13px] font-semibold text-secondary hover:underline">
                Inspect graph & details →
              </a>
            </div>
          </article>
        ))
      )}
    </div>
  );
}
