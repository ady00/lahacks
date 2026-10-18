import { get } from "@/lib/api";
import type { IrsReport, IrsRule, Witness } from "@/lib/types";
import { expr, factLabel, requireText, valueText } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { VerdictChip } from "@/components/VerdictChip";
import { Chevron } from "@/components/icons";
import { btn, btnPrimary, card, eyebrow, h2, mono, muted, row } from "@/lib/ui";

const SOURCES: [string, string][] = [
  ["IRC §274: disallowance of certain entertainment, meal, gift and travel expenses", "https://www.law.cornell.edu/uscode/text/26/274"],
  ["Reg. §1.274-5: substantiation, including the $75 receipt rule and the lodging exception", "https://www.law.cornell.edu/cfr/text/26/1.274-5"],
  ["Reg. §1.62-2: accountable plans and the 60-day substantiation safe harbor", "https://www.law.cornell.edu/cfr/text/26/1.62-2"],
  ["Reg. §1.274-11: entertainment after the Tax Cuts and Jobs Act", "https://www.law.cornell.edu/cfr/text/26/1.274-11"],
  ["Rev. Rul. 99-7: commuting versus deductible local travel", "https://www.irs.gov/pub/irs-drop/rr-99-7.pdf"],
  ["Notice 2026-10: 2026 standard mileage rates (72.5 cents a mile for business)", "https://www.irs.gov/tax-professionals/standard-mileage-rates"],
  ["Publication 463: travel, gift and car expenses", "https://www.irs.gov/publications/p463"],
];

const NOT_ENCODED = [
  "\"Lavish or extravagant\" meals (§274(k)): the Code sets no dollar figure, so there is nothing to prove; the company's per-person caps stand in for it.",
  "Federal per diem rates: this company reimburses actual cost, so the per diem substitution rules in Rev. Proc. 2019-48 never apply.",
  "Employee achievement awards (§274(j), $400 and $1,600 caps) and club dues (§274(a)(3)): no expense type for them yet.",
  "Gifts to employees are compensation, not §274(b) business gifts; the $25 rule here is written for gifts to clients and partners. Cash and gift cards are never de minimis (Reg. §1.132-6(c)).",
  "This is a coding and substantiation check, not tax advice. It says what the rules force; a tax professional decides the return.",
];

// The whole page is the API's Z3 report: every number, witness and core below was proven on this request.
export default async function IrsPage() {
  const r = await get<IrsReport>("/policy/irs");
  const total = r.rules.reduce((ms, x) => ms + x.ms, 0);
  const tiles: [string, string, string][] = [
    [String(r.summary.rules), "statutory checks", "each proven both ways on this page load"],
    [String(r.summary.implied_by_company), "already forced by company policy", "Z3 proved the company rules imply them"],
    [String(r.summary.irs_only), "caught only by this layer", "turn the layer off and these go unchecked"],
    [`${total.toFixed(0)} ms`, "to prove all of it", `${r.rules.length * 3} solver questions, ${r.audit.dead.length + r.audit.conflicts.length} consistency problems`],
  ];
  return (
    <div className="animate-fade-in-up space-y-6">
      <PageHeader
        title="IRS checks"
        text="The statutory layer under every purchase check: which account it posts to, how much of it is deductible, and what the IRS needs as evidence. Each rule cites its section and is proven both ways by Z3, live."
      >
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
          The IRS layer is off. Purchase checks now prove against company policy only: no account is derived and no deductibility is recorded. The report below still runs on the full pack so you can see what is going unchecked.
        </p>
      )}

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {tiles.map(([n, label, note]) => (
          <div key={label} className={`${card} p-5 hover:shadow-[0_14px_30px_-6px_rgba(15,23,42,0.08)]`}>
            <div className="font-serif text-[28px] font-bold tracking-[-0.03em] text-ink">{n}</div>
            <div className="text-[13px] font-medium text-[#1E293B]">{label}</div>
            <div className={`mt-1 text-[12px] ${muted}`}>{note}</div>
          </div>
        ))}
      </section>

      <section className={`${card} p-7`}>
        <div className="flex items-center gap-2.5">
          <span className="text-secondary"><Chevron /></span>
          <h2 className={h2}>Try it on stage</h2>
        </div>
        <ol className={`mt-3 list-decimal space-y-1.5 pl-5 text-sm ${muted}`}>
          <li>Check <span className="font-medium text-ink">“Client dinner Thursday with Acme&apos;s CFO, about $48.”</span> The case shows <span className="font-mono text-xs">meals_50 · 50% deductible</span> derived by IRS-meal, with nobody entering it.</li>
          <li>Check <span className="font-medium text-ink">“Lakers tickets with the Acme team, $340”</span>: entertainment, 0% deductible since 2018, posted to <span className="font-mono text-xs">entertainment_0</span>.</li>
          <li>Check <span className="font-medium text-ink">“Drove 120 miles to the client site, $95”</span>: over the 72.5¢ standard rate, so the fix is “keep it at or under $87”; the excess would be wages.</li>
          <li>Switch the layer off above, check the dinner again: same company verdict, no account, no deductibility. Switch it back on.</li>
        </ol>
      </section>

      <section className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className={h2}>{`Statutory rules, proven both ways (${r.rules.length})`}</h2>
          <span className={`text-[12px] ${muted}`}>{`Live policy ${r.policy_version}`}</span>
        </div>
        {r.rules.map((x) => (
          <RuleReport key={x.id} x={x} />
        ))}
      </section>

      <section className={`${card} space-y-4 p-7`}>
        <h2 className={h2}>How the formal tests work</h2>
        <p className={`text-sm ${muted}`}>
          Every rule is one formula, <span className="font-mono text-xs text-ink">when ⇒ require</span>, over the typed facts of a purchase. Z3 is an SMT solver: given formulas, it either finds values for every fact that make them all true, or proves that none exist. The page asks it four questions per rule, on every load.
        </p>
        <ol className="space-y-3 text-sm">
          {[
            ["Build a purchase that breaks it", "Z3 is asked for facts with the condition true and the requirement false, while every other rule is a soft constraint (MaxSAT). The engine then re-proves that purchase exactly as it would a real one: the verdict must be a violation naming this rule, and the unsat core lists the facts that decided it. When another rule cannot be kept (a $75 expense without a receipt also breaks the company's $50 receipt rule), it is listed as “also trips”."],
            ["Build a purchase that satisfies it", "Facts with the condition true and every rule true. The engine must call it compliant and list this rule as applied. A prohibition (require: never) has no such purchase: once its condition holds, the answer is simply no, and the page says so instead of inventing one."],
            ["Ask whether company policy already forces it", "Z3 checks whether the company rules together with “condition true, requirement false” are satisfiable. If not, the company layer alone already enforces the IRS rule, and the minimized unsat core names which company rules do it. The rest are caught only by this layer."],
            ["Check the layer is consistent", "No IRS rule whose condition can never hold, and no two rules that can both apply and disagree about the same purchase. The same audit runs on the Rules page for the whole policy."],
          ].map(([t, d], i) => (
            <li key={t} className="flex gap-3">
              <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-[#F0FDFA] font-mono text-[11px] font-semibold text-[#0F766E]">{i + 1}</span>
              <div>
                <div className="font-medium text-ink">{t}</div>
                <p className={`mt-0.5 ${muted}`}>{d}</p>
              </div>
            </li>
          ))}
        </ol>
        <p className={`text-sm ${muted}`}>
          Besides these solver-built witnesses, every rule has a hand-written boundary pair in <span className="font-mono text-xs text-ink">engine/test_policy_packs.py</span>: $74.99 against $75, 60 days against 61, 72.50 against 72.51 cents a mile. Those run under pytest; this page runs under Z3 against whatever policy is live, including rules added in Policy Studio.
        </p>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <div className={`${card} p-7`}>
          <h2 className={h2}>Not encoded, on purpose</h2>
          <ul className={`mt-3 list-disc space-y-1.5 pl-5 text-sm ${muted}`}>
            {NOT_ENCODED.map((t) => <li key={t}>{t}</li>)}
          </ul>
        </div>
        <div className={`${card} p-7`}>
          <h2 className={h2}>Sources</h2>
          <ul className="mt-3 space-y-1.5 text-sm">
            {SOURCES.map(([t, href]) => (
              <li key={href}>
                <a href={href} target="_blank" rel="noreferrer" className="text-secondary hover:underline">{t}</a>
              </li>
            ))}
          </ul>
          <p className={`mt-3 text-[12px] ${muted}`}>Checked October 18, 2026. Citations are also on each rule in <span className="font-mono text-[11px]">engine/irs_pack.json</span>.</p>
        </div>
      </section>
    </div>
  );
}

function RuleReport({ x }: { x: IrsRule }) {
  return (
    <div className={`${row} space-y-4 hover:translate-y-0`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 flex-1 flex-wrap items-start gap-x-5 gap-y-1 sm:flex-nowrap">
          <div className="w-32 shrink-0">
            <div className="font-serif text-[13px] font-bold text-ink">{`Rule ${x.id}`}</div>
            <a href={x.url} target="_blank" rel="noreferrer" className="text-[11px] font-medium text-[#0D9488] hover:underline">{x.cite}</a>
          </div>
          <div className="min-w-0">
            <p className="text-[13px] font-medium text-[#1E293B]">{x.text}</p>
            <p className={`${mono} break-words`}>{`when: ${expr(x.when)}  |  ${requireText(x.require).toLowerCase()}`}</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {x.implied_by.length > 0 ? (
            <span className="rounded-md border border-[#E0E7FF] bg-[#EEF2FF] px-2 py-0.5 text-[11px] font-semibold text-[#4338CA]" title="Z3 proved these company rules already force this requirement">
              {`Also forced by ${x.implied_by.join(", ")}`}
            </span>
          ) : (
            <span className="rounded-md border border-[#CCFBF1] bg-[#F0FDFA] px-2 py-0.5 text-[11px] font-semibold text-[#0F766E]">Only this layer catches it</span>
          )}
          {x.prohibition && <span className="rounded-md border border-[#FECACA] bg-[#FEF2F2] px-2 py-0.5 text-[11px] font-semibold text-[#B91C1C]">Prohibition</span>}
          <span className={`${mono} text-[11px]`}>{`${x.ms.toFixed(1)} ms`}</span>
        </div>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <WitnessBox title="Z3 built a purchase that breaks it" w={x.breaks} facts={x.facts_used} rule={x.id} />
        {x.prohibition ? (
          <div className="rounded-lg border border-dashed border-[#E2E8F0] p-3.5 text-sm">
            <p className={eyebrow}>No satisfying purchase exists</p>
            <p className={`mt-2 ${muted}`}>The requirement is “never”. Once the condition holds there is nothing to attach or approve; the engine returns a violation with no fix.</p>
          </div>
        ) : (
          <WitnessBox title="…and one that satisfies it" w={x.holds} facts={x.facts_used} rule={x.id} />
        )}
      </div>
    </div>
  );
}

function WitnessBox({ title, w, facts, rule }: { title: string; w: Witness | null | undefined; facts: string[]; rule: string }) {
  if (!w) return <p className={`text-sm ${muted}`}>Z3 found no such purchase.</p>;
  const core = w.because[rule] ?? [];
  const bad = w.verdict === "violation";
  return (
    <div className={`rounded-lg border p-3.5 text-sm ${bad ? "border-[#FECACA] bg-[#FFF5F5]" : "border-[#DCFCE7] bg-[#F0FDF4]"}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className={eyebrow}>{title}</p>
        <VerdictChip verdict={w.verdict} />
      </div>
      <dl className="mt-2.5 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[13px]">
        {facts.map((f) => (
          <div key={f} className="contents">
            <dt className={`${muted} ${core.includes(f) ? "font-semibold text-[#B91C1C]" : ""}`}>{factLabel(f)}</dt>
            <dd className="font-medium text-ink">{valueText(f, w.facts[f])}</dd>
          </div>
        ))}
      </dl>
      <p className={`mt-2.5 text-[12px] ${muted}`}>
        {bad
          ? `Engine re-proved it: violation of ${rule}. Unsat core: ${core.map(factLabel).join(", ")}.${w.also.length ? ` Also trips ${w.also.join(", ")}.` : ""}`
          : `Engine re-proved it: compliant, ${rule} applied and held.`}
      </p>
    </div>
  );
}
