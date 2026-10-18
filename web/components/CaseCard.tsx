import type { Case } from "@/lib/types";
import { factLabel, fixLine, pct, sourceLabel, usd, valueText, when } from "@/lib/format";
import { VerdictChip } from "./VerdictChip";
import { card, h2, muted } from "@/lib/ui";

const th = "py-1 pr-3 font-normal";
const td = "py-1.5 pr-3 align-top";

/** The one case shape, rendered the same on every page. The page above it says the verdict in words. */
export function CaseCard({ c }: { c: Case }) {
  return (
    <article className={`${card} animate-fade-in-up space-y-5 p-7`}>
      <header className="flex flex-wrap items-center gap-3 text-sm">
        <VerdictChip verdict={c.verdict} />
        <span className={muted}>{`Checked ${when(c.created_at)}`}</span>
        <span className={`font-mono text-xs ${muted}`}>{c.case_id}</span>
      </header>

      <p className="text-lg font-medium break-words text-[#0F172A]">“{c.text}”</p>

      {c.product && (
        <a href={c.product.url} target="_blank" rel="noreferrer" className="flex items-center gap-4 rounded-lg border border-[#E2E8F0] bg-white p-3 text-sm transition-colors hover:border-[#CBD5E1]">
          {c.product.image && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={c.product.image} alt="" className="size-14 shrink-0 rounded-md object-contain" />
          )}
          <span className="min-w-0">
            <span className="block truncate font-medium text-[#0F172A]">{c.product.title ?? `Product link on ${c.product.vendor}`}</span>
            <span className={`block text-xs ${muted}`}>
              {c.product.error
                ? `Could not read the page (${c.product.error}). Add the amount yourself.`
                : [c.product.vendor, c.product.category, c.product.price != null ? usd(c.product.price) : "price not found, add the amount"].filter(Boolean).join(" · ")}
            </span>
          </span>
        </a>
      )}

      <p className="rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] p-3.5 text-sm transition-colors hover:border-[#CBD5E1]">{c.explanation}</p>

      {(c.facts.coded_account || c.facts.deductible) && (
        <a href="/irs" className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-[#CCFBF1] bg-[#F0FDFA] px-3.5 py-2.5 text-sm text-[#0F766E] transition-colors hover:border-[#5EEAD4]">
          <span className="text-[11px] font-bold uppercase tracking-[0.06em]">Tax treatment</span>
          {c.facts.coded_account && <span className="font-medium">{valueText("coded_account", c.facts.coded_account.value)}</span>}
          {c.facts.deductible && <span className="font-medium">{`${c.facts.deductible.value} deductible`}</span>}
          <span className="ml-auto text-xs text-[#0D9488]">derived by the IRS layer, not entered by anyone →</span>
        </a>
      )}

      {c.approval && (
        <div className={`flex items-center gap-2 rounded-lg border px-4 py-2.5 text-sm shadow-2xs ${c.approval.approved ? "border-green-200 bg-green-50/80 text-green-800" : "border-red-200 bg-red-50/80 text-red-800"}`}>
          <span className={`inline-block size-2 rounded-full ${c.approval.approved ? "bg-green-600" : "bg-red-600"} animate-pulse`} />
          <span className="font-medium">{`${c.approval.approved ? "Approved" : "Rejected"} by ${c.approval.approver} on ${when(c.approval.at)}`}</span>
        </div>
      )}

      {c.authorization && (
        <section className="relative overflow-hidden rounded-xl border-2 border-emerald-400 bg-gradient-to-br from-emerald-50 via-green-50 to-teal-50 p-5 shadow-sm transition-all duration-200 hover:shadow-md">
          <div className="flex items-center justify-between gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-300 bg-emerald-100/80 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-800">
              <span className="relative flex size-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-500 opacity-75" />
                <span className="relative inline-flex size-1.5 rounded-full bg-emerald-600" />
              </span>
              Mock Visa Card Issued
            </span>
            <span className="font-mono text-[11px] font-medium text-emerald-700">Active Limit</span>
          </div>
          <h2 className="mt-2 font-serif text-[20px] font-bold tracking-tight text-emerald-950">
            {`Card authorized for up to ${usd(c.authorization.amount_limit)}`}
          </h2>
          <p className="mt-1 text-sm text-emerald-800">{`${c.authorization.merchant_category} · expires ${when(c.authorization.expires_at)}`}</p>
          <div className="mt-3 flex items-center justify-between rounded-lg border border-emerald-200 bg-white/70 px-3 py-1.5 text-xs">
            <span className="font-medium text-emerald-900">Z3 Proof Certificate</span>
            <span className="break-all font-mono text-[11px] text-emerald-700">{c.authorization.proof_hash}</span>
          </div>
        </section>
      )}

      {c.violations.length > 0 && (
        <section className="space-y-2.5">
          <h2 className={h2}>Rules this breaks</h2>
          <ul className="space-y-2 text-sm">
            {c.violations.map((v) => (
              <li key={v.rule} className="rounded-lg border border-[#F1F5F9] bg-[#FFF5F5] p-3 transition-all hover:border-red-200 hover:shadow-2xs">
                <div className="flex items-center gap-2">
                  <span className="rounded bg-red-100 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-red-800">{`Rule ${v.rule}`}</span>
                  <span className="font-medium text-zinc-900">{v.text}</span>
                </div>
                <div className={`mt-1.5 text-xs ${muted}`}>{`Decided by: ${v.because.map(factLabel).join(", ")}`}</div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {c.fix === null ? (
        <p className="rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] p-3 text-sm text-[#64748B]">No change you control makes this compliant.</p>
      ) : c.fix.length > 0 ? (
        <section className="rounded-lg border border-amber-200 bg-amber-50/50 p-4">
          <h2 className="mb-2 font-serif text-[15px] font-bold text-amber-950">What would make it compliant</h2>
          <ul className="list-disc space-y-1 pl-5 text-sm text-amber-900">
            {c.fix.map((s) => (
              <li key={s.fact}>{fixLine(s)}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <section>
        <h2 className={`mb-2 ${h2}`}>What the rules saw</h2>
        <div className="overflow-x-auto rounded-lg border border-[#F1F5F9]">
          <table className="w-full text-sm">
          <thead className={`bg-[#F8FAFC] text-left ${muted}`}>
            <tr>
              <th className={`${th} pl-4`}>Fact</th>
              <th className={th}>Value</th>
              <th className={th}>Where it came from</th>
              <th className={`${th} pr-4`} title="How sure the text reader was; blank when the value was not read from text">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(c.facts).map(([name, f]) => (
              <tr key={name} className="border-t border-[#F1F5F9] transition-colors duration-150 hover:bg-[#F8FAFC]">
                <td className={`${td} pl-4`}>
                  {factLabel(name)} <span className={`font-mono text-xs ${muted}`}>{name}</span>
                </td>
                <td className={`${td} font-medium text-zinc-900`}>{valueText(name, f.value)}</td>
                <td className={`${td} ${muted}`}>{sourceLabel(f.source)}</td>
                <td className={`${td} pr-4 font-mono`}>{pct(f.p)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </section>
    </article>
  );
}
