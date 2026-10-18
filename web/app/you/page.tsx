import { get } from "@/lib/api";
import { requireUser } from "@/lib/session";
import type { ApplicableOut, ApplicableRule, EmployeeList } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { btn, card, eyebrow, h2, muted, row } from "@/lib/ui";

const LAYER: Record<string, [string, string]> = { company: ["Company policy", "text-[#6366F1]"], irs: ["IRS", "text-[#0D9488]"] };

const date = (iso: string) => new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeZone: "UTC" }).format(new Date(`${iso}T00:00:00Z`));
const days = (n: number) => `${n} more ${n === 1 ? "day" : "days"}`;
// ponytail: the rule JSON is not on this route, so the reason is read off the id and the sentence
const why = (r: ApplicableRule) => (r.id.startsWith("5.") || /intern|contractor/i.test(r.text) ? "because of your role" : "for your role and tenure");

// Everything here is the API's Z3 result for this person: no model writes any of it.
export default async function YouPage() {
  const user = await requireUser();
  const [{ employee, facts, rules }, { employees }] = await Promise.all([
    get<ApplicableOut>(`/employees/${encodeURIComponent(user.employee_id)}/rules`),
    get<EmployeeList>("/employees"),
  ]);
  const manager = employees.find((e) => e.employee_id === employee.manager_id)?.name || (employee.manager_id ? employee.manager_id : "none");
  const tenure = typeof facts.tenure_days === "number" ? `${facts.tenure_days} ${facts.tenure_days === 1 ? "day" : "days"}` : "unknown (no start date)";
  const applies = rules.filter((r) => r.applies);
  const never = rules.filter((r) => !r.applies);
  const record: [string, string][] = [
    ["Name", employee.name],
    ["Job title", employee.job_title || "—"],
    ["Department", employee.department || "—"],
    ["Level", employee.level || "—"],
    ["Location", employee.location || "—"],
    ["Start date", employee.start_date ? date(employee.start_date) : "—"],
    ["Tenure", tenure],
    ["Manager", manager],
    ["Role", employee.role],
  ];
  return (
    <div className="animate-fade-in-up space-y-6">
      <PageHeader title="What applies to you" text="The rules that apply to your role and tenure.">
        <a href="/rules" className={btn}>All rules</a>
      </PageHeader>

      <section className={`${card} p-7 hover:shadow-[0_14px_30px_-6px_rgba(15,23,42,0.08)]`}>
        <p className={eyebrow}>From your employee record</p>
        <dl className="mt-3 grid grid-cols-2 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
          {record.map(([k, v]) => (
            <div key={k} className="rounded-lg p-2 transition-colors hover:bg-slate-50">
              <dt className={`text-[12px] ${muted}`}>{k}</dt>
              <dd className="font-medium text-[#1E293B]">{v}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="mt-9 space-y-4">
        <h2 className={h2}>{`Applies to you now (${applies.length})`}</h2>
        {(["company", "irs"] as const).map((layer) => {
          const group = applies.filter((r) => r.layer === layer);
          return group.length ? (
            <div key={layer} className="space-y-3">
              <p className={eyebrow}>{LAYER[layer][0]}</p>
              {group.map((r) => (
                <div key={r.id} className={`${row} flex flex-wrap items-center justify-between gap-3 transition-all duration-200 hover:border-slate-300 hover:shadow-xs hover:-translate-y-px`}>
                  <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-5 gap-y-1 sm:flex-nowrap">
                    <div className="w-24 shrink-0">
                      <div className="font-serif text-[13px] font-bold text-ink">{`Rule ${r.id}`}</div>
                      <div className={`text-[11px] font-medium ${LAYER[r.layer]?.[1] ?? muted}`}>{LAYER[r.layer]?.[0] ?? r.layer}</div>
                    </div>
                    <p className="text-[13px] font-medium text-[#1E293B]">{r.text}</p>
                  </div>
                  {r.days_left != null && (
                    <span className="rounded bg-[#FFFBEB] px-2 py-0.5 text-[11px] font-semibold text-[#D97706]">{`for ${days(r.days_left)}`}</span>
                  )}
                </div>
              ))}
            </div>
          ) : null;
        })}
      </section>

      {never.length > 0 && (
        <section className="mt-9 space-y-2">
          <h2 className={h2}>{`Never applies to you (${never.length})`}</h2>
          <p className={`text-[12px] ${muted}`}>Z3 proved these rules cannot fire for a person with your record.</p>
          <ul className={`space-y-1 text-[13px] ${muted}`}>
            {never.map((r) => (
              <li key={r.id}>
                <span className="font-mono text-[11px]">{r.id}</span> {r.text} <span className="text-[#94A3B8]">{`· ${why(r)}`}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className={`${card} mt-9 space-y-2 p-7 text-sm`}>
        <h2 className={h2}>What this page will not do</h2>
        <ul className={`list-disc space-y-1 pl-5 ${muted}`}>
          <li>It does not decide your pay, your employment or what you can access. It only says which purchase rules apply.</li>
          <li>A purchase that needs approval always waits for a human manager.</li>
          <li>When a fact is unknown, the check asks you instead of guessing.</li>
        </ul>
      </section>
    </div>
  );
}
