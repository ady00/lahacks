import { get } from "@/lib/api";
import type { IrsReport, IrsRule } from "@/lib/types";
import { expr, requireText } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { btn, btnPrimary, card, h2, mono, muted, row } from "@/lib/ui";

const ACCOUNTS: [string, string, string][] = [
  ["meals_50", "Business meals", "The company deducts half the cost. §274(n)(1)."],
  ["meals_100", "Meals at a company-wide event", "Recreational events for employees are fully deductible. §274(e)(4)."],
  ["entertainment_0", "Entertainment", "Tickets, games, shows, golf, clubs. Not deductible since 2018. §274(a)(1)."],
  ["travel", "Travel", "Flights, trains, rental cars, lodging, rides, parking, mileage: travel away from home. §162(a)(2)."],
  ["office", "Office expenses", "Equipment, supplies, software, internet, phone, co-working, shipping: ordinary business expenses. §162(a)."],
  ["other", "Other", "Books, development, gifts, swag and the rest."],
];

const DEDUCTIBLE: [string, string][] = [
  ["0%", "None of it reduces taxable income (entertainment)."],
  ["50%", "Half of it does (business meals)."],
  ["100%", "All of it does (company-event meals)."],
  ["limited", "Part of it does not: a companion's share of travel, or a gift above $25 a recipient."],
  ["blank", "No IRS rule caps it; the account alone says how it is treated."],
];

const SOURCES: [string, string][] = [
  ["IRC §274", "https://www.law.cornell.edu/uscode/text/26/274"],
  ["Reg. §1.274-5", "https://www.law.cornell.edu/cfr/text/26/1.274-5"],
  ["Reg. §1.62-2", "https://www.law.cornell.edu/cfr/text/26/1.62-2"],
  ["Rev. Rul. 99-7", "https://www.irs.gov/pub/irs-drop/rr-99-7.pdf"],
  ["Notice 2026-10", "https://www.irs.gov/tax-professionals/standard-mileage-rates"],
  ["Pub. 463", "https://www.irs.gov/publications/p463"],
];

// The rules, their citations and the layer's status come from the API; the meanings are written here.
export default async function IrsPage() {
  const r = await get<IrsReport>("/policy/irs");
  const problems = r.audit.dead.length + r.audit.conflicts.length;
  return (
    <div className="animate-fade-in-up space-y-6">
      <PageHeader title="IRS layer" text="Company policy decides whether you can buy it. This layer adds the tax treatment: the account it posts to, how much is deductible, and a note when an IRS rule is not met. It never changes the verdict.">
        <form method="post" action="/act/irs-layer" className="flex items-center gap-3">
          <input type="hidden" name="irs" value={r.enabled ? "false" : "true"} />
          <span className="flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 shadow-[0_2px_4px_rgba(0,0,0,0.06)]">
            <span className="relative flex size-2">
              {r.enabled && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#0D9488] opacity-75" />}
              <span className={`relative inline-flex size-2 rounded-full ${r.enabled ? "bg-[#0D9488]" : "bg-slate-300"}`} />
            </span>
            <span className="font-serif text-[11.5px] font-semibold text-ink">{r.enabled ? "IRS layer: on" : "IRS layer: off"}</span>
          </span>
          <button className={r.enabled ? btn : btnPrimary}>{r.enabled ? "Switch off" : "Switch on"}</button>
        </form>
      </PageHeader>

      {!r.enabled && (
        <p role="status" className="rounded-lg border border-amber-200 bg-amber-50/80 px-4 py-3 text-sm text-amber-900">
          Off: cases show no account, deductibility or IRS notes. Verdicts are unchanged either way.
        </p>
      )}

      <section className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        <div className={`${card} p-7`}>
          <h2 className={h2}>Posts to account</h2>
          <p className={`mt-1 text-[12px] ${muted}`}>Derived from the expense type by the rules below; the ledger row is coded with it.</p>
          <dl className="mt-4 space-y-3 text-sm">
            {ACCOUNTS.map(([v, name, meaning]) => (
              <div key={v} className="grid grid-cols-[9.5rem_1fr] gap-x-4">
                <dt>
                  <div className="font-medium text-ink">{name}</div>
                  <div className={`${mono}`}>{v}</div>
                </dt>
                <dd className={muted}>{meaning}</dd>
              </div>
            ))}
          </dl>
        </div>
        <div className="space-y-6">
          <div className={`${card} p-7`}>
            <h2 className={h2}>Deductible</h2>
            <p className={`mt-1 text-[12px] ${muted}`}>How much of the amount the company can deduct.</p>
            <dl className="mt-4 space-y-2 text-sm">
              {DEDUCTIBLE.map(([v, meaning]) => (
                <div key={v} className="grid grid-cols-[4rem_1fr] gap-x-4">
                  <dt className="font-mono text-[12px] font-semibold text-ink">{v}</dt>
                  <dd className={muted}>{meaning}</dd>
                </div>
              ))}
            </dl>
          </div>
          <div className={`${card} p-7`}>
            <h2 className={h2}>IRS note</h2>
            <p className={`mt-2 text-sm ${muted}`}>
              An IRS rule the purchase does not meet. The purchase may still be allowed; the note tells finance what follows: get the receipt, treat the excess as wages, do not reimburse a commute tax-free.
            </p>
          </div>
        </div>
      </section>

      <section className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className={h2}>{`Rules (${r.rules.length})`}</h2>
          <span className={`text-[12px] ${muted}`}>
            {problems ? `${problems} consistency ${problems === 1 ? "problem" : "problems"}` : "Consistent (Z3 proved)"}
            {` · ${r.summary.implied_by_company} already forced by company policy`}
          </span>
        </div>
        {r.rules.map((x) => (
          <RuleLine key={x.id} x={x} />
        ))}
      </section>

      <p className={`text-[12px] ${muted}`}>
        Not encoded: lavish or extravagant (§274(k)), per diem rates, achievement awards (§274(j)), club dues (§274(a)(3)), gifts to employees as compensation. A coding check, not tax advice. Sources:{" "}
        {SOURCES.map(([t, href], i) => (
          <span key={href}>
            {i > 0 && ", "}
            <a href={href} target="_blank" rel="noreferrer" className="text-secondary hover:underline">{t}</a>
          </span>
        ))}
        .
      </p>
    </div>
  );
}

function RuleLine({ x }: { x: IrsRule }) {
  return (
    <div className={`${row} flex flex-wrap items-center justify-between gap-3`}>
      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-5 gap-y-1 sm:flex-nowrap">
        <div className="w-32 shrink-0">
          <div className="font-serif text-[13px] font-bold text-ink">{`Rule ${x.id}`}</div>
          <a href={x.url} target="_blank" rel="noreferrer" className="text-[11px] font-medium text-[#0D9488] hover:underline">{x.cite}</a>
        </div>
        <div className="min-w-0">
          <p className="text-[13px] font-medium text-[#1E293B]">{x.text}</p>
          <p className={`${mono} break-words sm:truncate`}>{`when: ${expr(x.when)}  |  ${requireText(x.require).toLowerCase()}`}</p>
        </div>
      </div>
      {x.implied_by.length > 0 && (
        <span className="rounded-md border border-[#E0E7FF] bg-[#EEF2FF] px-2 py-0.5 text-[11px] font-semibold text-[#4338CA]" title="Z3 proved these company rules already force this requirement">
          {`Also forced by ${x.implied_by.join(", ")}`}
        </span>
      )}
    </div>
  );
}
