import type { Case } from "@/lib/types";
import { factLabel, fixLine, pct, sourceLabel, usd, valueText, when } from "@/lib/format";
import { VerdictChip } from "./VerdictChip";
import { card, h2, muted } from "@/lib/ui";

const th = "py-1 pr-3 font-normal";
const td = "py-1.5 pr-3 align-top";

/** The one case shape, rendered the same on every page. The page above it says the verdict in words. */
export function CaseCard({ c }: { c: Case }) {
  return (
    <article className={`${card} space-y-5 p-7`}>
      <header className="flex flex-wrap items-center gap-3 text-sm">
        <VerdictChip verdict={c.verdict} />
        <span className={muted}>{`Checked ${when(c.created_at)}`}</span>
        <span className={`font-mono text-xs ${muted}`}>{c.case_id}</span>
      </header>

      <p className="text-lg break-words">“{c.text}”</p>

      <p className="rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] p-3.5 text-sm">{c.explanation}</p>

      {c.approval && (
        <p className={`rounded px-3 py-2 text-sm ${c.approval.approved ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"}`}>
          {`${c.approval.approved ? "Approved" : "Rejected"} by ${c.approval.approver} on ${when(c.approval.at)}`}
        </p>
      )}

      {c.authorization && (
        <section className="rounded-lg border border-green-300 bg-green-50 p-4 text-sm">
          <h2 className={h2}>{`Card authorized for up to ${usd(c.authorization.amount_limit)}`}</h2>
          <p className="mt-1">{`${c.authorization.merchant_category} · expires ${when(c.authorization.expires_at)}`}</p>
          <p className={`mt-2 break-all font-mono text-xs ${muted}`}>{`Proof ${c.authorization.proof_hash}`}</p>
        </section>
      )}

      {c.violations.length > 0 && (
        <section>
          <h2 className={`mb-2 ${h2}`}>Rules this breaks</h2>
          <ul className="space-y-2 text-sm">
            {c.violations.map((v) => (
              <li key={v.rule}>
                <span className="font-mono text-xs font-semibold">{`Rule ${v.rule}`}</span> {v.text}
                <div className={`text-xs ${muted}`}>{`Decided by: ${v.because.map(factLabel).join(", ")}`}</div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {c.fix === null ? (
        <p className="text-sm">No change you control makes this compliant.</p>
      ) : c.fix.length > 0 ? (
        <section>
          <h2 className={`mb-2 ${h2}`}>What would make it compliant</h2>
          <ul className="list-disc pl-5 text-sm">
            {c.fix.map((s) => (
              <li key={s.fact}>{fixLine(s)}</li>
            ))}
          </ul>
        </section>
      ) : null}

      <section>
        <h2 className={`mb-2 ${h2}`}>What the rules saw</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
          <thead className={`text-left ${muted}`}>
            <tr>
              <th className={th}>Fact</th>
              <th className={th}>Value</th>
              <th className={th}>Where it came from</th>
              <th className={th} title="How sure the text reader was; blank when the value was not read from text">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(c.facts).map(([name, f]) => (
              <tr key={name} className="border-t border-[#F1F5F9]">
                <td className={td}>
                  {factLabel(name)} <span className={`font-mono text-xs ${muted}`}>{name}</span>
                </td>
                <td className={`${td} font-medium`}>{valueText(name, f.value)}</td>
                <td className={`${td} ${muted}`}>{sourceLabel(f.source)}</td>
                <td className={td}>{pct(f.p)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </section>
    </article>
  );
}
