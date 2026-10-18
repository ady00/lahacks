import { get, post } from "@/lib/api";
import { requireUser } from "@/lib/session";
import type { ApplicableOut, EmployeeList, PolicyAudit, PolicyOut } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { RuleRow } from "@/components/RuleRow";
import type { Rule } from "@/lib/types";
import { Bolt, Chevron, Sparkle, Wand } from "@/components/icons";
import { btn, btnPrimary, card, chip, eyebrow, h2, mono, muted } from "@/lib/ui";

const EXAMPLES = [
  "Client dinner Thursday with Acme's CFO, about $48.",
  "Uber to the airport, $62",
  "Datadog subscription for the team, $650 a month",
  "Team lunch at the offsite, $320 for 8 people",
  "iPad for customer demos https://www.amazon.com/dp/B09V3KXJPB",
];

// The home page is the purchase check: a native GET form to /check, which POSTs the API server-side and
// redirects to the case, so a refresh never creates a second case.
export default async function Home() {
  const user = await requireUser();
  const [policy, audit, { employees }, you] = await Promise.all([
    get<PolicyOut>("/policy"),
    post<PolicyAudit>("/policy/audit"),
    get<EmployeeList>("/employees"),
    get<ApplicableOut>(`/employees/${encodeURIComponent(user.employee_id)}/rules`).catch(() => null),
  ]);
  const probation = you?.rules.filter((r) => r.applies && r.days_left != null) ?? [];
  const rules = policy.rules as Rule[];
  const role = employees.find((e) => e.employee_id === user.employee_id)?.role ?? "employee";
  const conflicts = audit.conflicts.length + audit.dead.length;
  const first = user.name.split(" ")[0] || user.name;
  return (
    <>
      <PageHeader
        title={`Can I buy this, ${first}?`}
        text="Describe it in your own words or paste a product link. You get a proven answer: allowed, needs approval, or one more question."
      >
        <a href="/ledger" className={btn}>Open ledger</a>
        <a href="/rules" className={btn}>See the rules</a>
      </PageHeader>
      {probation.length > 0 && (
        <p className={`-mt-3 pb-5 text-[12px] ${muted}`}>
          {`${probation.length} first-90-days ${probation.length === 1 ? "rule applies" : "rules apply"} to you for ${probation[0].days_left} more days · `}
          <a href="/you" className="font-semibold text-secondary hover:underline">See what applies to you</a>
        </p>
      )}

      <form method="get" action="/check" className={`${card} animate-fade-in-up hover:shadow-[0_16px_36px_-6px_rgba(15,23,42,0.1)]`}>
        <div className="space-y-3.5 border-b border-[#F1F5F9] bg-gradient-to-b from-[#FAFAF9] to-white px-5 pb-5 pt-6 sm:px-7">
          <div className="flex items-center gap-2">
            <span className="flex size-5 items-center justify-center rounded-md bg-[#EEF2FF] text-secondary shadow-xs transition-transform hover:rotate-12"><Sparkle /></span>
            <span className={eyebrow}>Purchase check</span>
          </div>
          <label className="flex min-h-13 items-center gap-3.5 rounded-xl border-[1.5px] border-secondary bg-white px-4.5 py-2 shadow-[0_0_0_3px_color-mix(in_oklab,var(--color-secondary)_15%,transparent),0_2px_6px_rgba(145,73,196,0.08)] transition-all duration-200 focus-within:shadow-[0_0_0_4px_color-mix(in_oklab,var(--color-secondary)_25%,transparent),0_4px_12px_rgba(145,73,196,0.15)]">
            <Wand />
            <input
              name="text"
              required
              autoFocus
              placeholder="Client dinner Thursday with Acme's CFO, about $48."
              className="min-w-0 grow bg-transparent font-serif text-[15px] font-medium tracking-[-0.01em] text-ink placeholder:text-[#94A3B8] focus:outline-none"
            />
            <kbd className="hidden rounded-md border border-[#E2E8F0] bg-[#F8FAFC] px-2.5 py-1 font-sans text-[11px] font-semibold text-[#64748B] transition-colors hover:bg-slate-100 sm:block">⏎ to check</kbd>
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[12px] font-medium text-[#94A3B8]">Try an example:</span>
            {EXAMPLES.map((e) => (
              <a key={e} href={`/check?text=${encodeURIComponent(e)}`} className={chip}>{e}</a>
            ))}
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-main bg-[#FAFAFA] px-5 py-3 font-serif text-[12px] sm:px-7">
          <div className="flex flex-wrap items-center gap-2">
            <span className="mr-1 font-semibold text-[#64748B]">Checked as:</span>
            <Token label="Who" value={user.name} />
            <Token label="Role" value={role} />
            <span className="flex items-center gap-1.5 rounded-md border border-main bg-white py-1 pl-2.5 pr-1.5 transition-colors focus-within:border-secondary">
              <span className="font-medium text-[#64748B]">Amount:</span>
              <span className="font-semibold text-ink">$</span>
              <input name="amount" type="number" step="0.01" min="0.01" placeholder="from text" className="w-20 bg-transparent font-sans font-semibold text-ink placeholder:font-normal placeholder:text-[#94A3B8] focus:outline-none" />
            </span>
          </div>
          <span className="flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 shadow-[0_2px_4px_rgba(0,0,0,0.06)] transition-all hover:scale-[1.02]">
            <span className="relative flex size-2">
              <span className={`absolute inline-flex h-full w-full animate-ping rounded-full ${conflicts ? "bg-amber-400" : "bg-secondary"} opacity-75`} />
              <span className={`relative inline-flex size-2 rounded-full ${conflicts ? "bg-amber-500" : "bg-secondary"}`} />
            </span>
            <span className="text-[11.5px] font-semibold text-ink">
              {conflicts ? `${conflicts} rule ${conflicts === 1 ? "problem" : "problems"} found` : `Policy consistent (Z3 proved)`}
            </span>
          </span>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 sm:px-7">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="text-secondary"><Chevron /></span>
            <span className="font-serif text-[13.5px] font-semibold text-ink">What happens next</span>
            <span className={`${mono} text-[12.5px] text-[#64748B]`}>{`(${rules.length} rules · policy ${policy.version.slice(0, 8)} · ${audit.conflicts.length} conflicts)`}</span>
          </div>
          <div className="flex items-center gap-3">
            <button type="reset" className={btn}>Clear</button>
            <button type="submit" className={btnPrimary}><Bolt /> Check the rules</button>
          </div>
        </div>
      </form>

      <section className="mt-9 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className={h2}>{`Active verified rules (${rules.length})`}</h2>
          <div className="flex items-center gap-2 text-[12px]">
            <span className="rounded-md bg-ink px-3 py-1.5 font-semibold text-white">{`All (${rules.length})`}</span>
            {(["company", "irs"] as const).map((l) => (
              <span key={l} className="rounded-md border border-[#E2E8F0] bg-white px-3 py-1.5 font-medium text-[#64748B]">
                {`${l === "irs" ? "IRS tax pack" : "Company"} (${rules.filter((r) => r.layer === l).length})`}
              </span>
            ))}
          </div>
        </div>
        {rules.slice(0, 3).map((r) => (
          <RuleRow key={r.id} r={r} />
        ))}
        <a href="/rules" className="inline-block font-serif text-[13px] font-semibold text-secondary hover:underline">
          {`See all ${rules.length} rules and the consistency proof →`}
        </a>
      </section>
    </>
  );
}

function Token({ label, value }: { label: string; value: string }) {
  return (
    <span className="flex items-center gap-1.5 rounded-md border border-main bg-white px-2.5 py-1.25">
      <span className="font-medium text-[#64748B]">{`${label}:`}</span>
      <span className="font-semibold text-ink">{value}</span>
    </span>
  );
}
