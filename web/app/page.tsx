import { get, post } from "@/lib/api";
import { requireUser } from "@/lib/session";
import type { EmployeeList, PolicyAudit, PolicyOut } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { RuleRow } from "@/components/RuleRow";
import type { Rule } from "@/lib/types";
import { Bolt, Chevron, Sparkle, Wand } from "@/components/icons";
import { btn, btnPrimary, card, chip, eyebrow, h2, mono } from "@/lib/ui";

const EXAMPLES = [
  "Client dinner Thursday with Acme's CFO, about $48.",
  "Uber to the airport, $62",
  "Datadog subscription for the team, $650 a month",
  "Team lunch at the offsite, $320 for 8 people",
];

// The home page is the purchase check: a native GET form to /check, which POSTs the API server-side and
// redirects to the case, so a refresh never creates a second case.
export default async function Home() {
  const user = await requireUser();
  const [policy, audit, { employees }] = await Promise.all([
    get<PolicyOut>("/policy"),
    post<PolicyAudit>("/policy/audit"),
    get<EmployeeList>("/employees"),
  ]);
  const rules = policy.rules as Rule[];
  const role = employees.find((e) => e.employee_id === user.employee_id)?.role ?? "employee";
  const conflicts = audit.conflicts.length + audit.dead.length;
  const first = user.name.split(" ")[0] || user.name;
  return (
    <>
      <PageHeader
        title={`Can I buy this, ${first}?`}
        text="Describe the purchase in your own words. Z3 checks every policy rule and proves the answer in a second: allowed, needs approval, or one more detail."
      >
        <a href="/ledger" className={btn}>Open ledger</a>
        <a href="/rules" className={btn}>See the rules</a>
      </PageHeader>

      <form method="get" action="/check" className={card}>
        <div className="space-y-3.5 border-b border-[#F1F5F9] bg-gradient-to-b from-[#FAFAF9] to-white px-5 pb-5 pt-6 sm:px-7">
          <div className="flex items-center gap-2">
            <span className="flex size-5 items-center justify-center rounded-md bg-[#EEF2FF] text-secondary"><Sparkle /></span>
            <span className={eyebrow}>Purchase check</span>
          </div>
          <label className="flex min-h-13 items-center gap-3.5 rounded-xl border-[1.5px] border-secondary bg-white px-4.5 py-2 shadow-[0_0_0_3px_color-mix(in_oklab,var(--color-secondary)_15%,transparent),0_2px_4px_#00000005]">
            <Wand />
            <input
              name="text"
              required
              autoFocus
              placeholder="Client dinner Thursday with Acme's CFO, about $48."
              className="min-w-0 grow bg-transparent font-serif text-[15px] font-medium tracking-[-0.01em] text-ink placeholder:text-[#94A3B8] focus:outline-none"
            />
            <kbd className="hidden rounded-md border border-[#E2E8F0] bg-[#F8FAFC] px-2.5 py-1 font-sans text-[11px] font-semibold text-[#64748B] sm:block">⏎ to check</kbd>
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
            <span className="flex items-center gap-1.5 rounded-md border border-main bg-white py-1 pl-2.5 pr-1.5">
              <span className="font-medium text-[#64748B]">Amount:</span>
              <span className="font-semibold text-ink">$</span>
              <input name="amount" type="number" step="0.01" min="0.01" placeholder="from text" className="w-20 bg-transparent font-sans font-semibold text-ink placeholder:font-normal placeholder:text-[#94A3B8] focus:outline-none" />
            </span>
          </div>
          <span className="flex items-center gap-1.5 rounded-full bg-white px-3 py-1 shadow-[0_2px_3px_#00000033]">
            <span className={`size-1.75 rounded-full ${conflicts ? "bg-amber-500" : "bg-secondary"}`} />
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
