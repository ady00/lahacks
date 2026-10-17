import type { Case } from "@/lib/types";
import { fixLine, pct } from "@/lib/format";
import { VerdictChip } from "./VerdictChip";

const muted = "text-zinc-500 dark:text-zinc-400";

/** The one case shape, rendered the same on every page. */
export function CaseCard({ c }: { c: Case }) {
  return (
    <article className="space-y-5 rounded-lg border border-zinc-200 p-5 dark:border-zinc-800">
      <header className="flex items-center gap-3">
        <VerdictChip verdict={c.verdict} />
        <span className="font-mono text-sm">{c.case_id}</span>
        <span className={`text-sm ${muted}`}>{c.employee_id}</span>
      </header>

      <p className="text-lg">“{c.text}”</p>

      <p className="rounded bg-zinc-100 p-3 text-sm dark:bg-zinc-900">{c.explanation}</p>

      {c.awaiting_approval && (
        <p className="rounded bg-amber-100 px-3 py-2 text-sm text-amber-800">Waiting for manager approval</p>
      )}

      <section>
        <h2 className="mb-2 font-semibold">Facts</h2>
        <table className="w-full text-sm">
          <thead className={`text-left ${muted}`}>
            <tr>
              <th className="py-1 font-normal">Fact</th>
              <th className="py-1 font-normal">Value</th>
              <th className="py-1 font-normal">Source</th>
              <th className="py-1 font-normal">p</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(c.facts).map(([name, f]) => (
              <tr key={name} className="border-t border-zinc-100 dark:border-zinc-800">
                <td className="py-1 font-mono">{name}</td>
                <td className="py-1">{String(f.value)}</td>
                <td className={`py-1 ${muted}`}>{f.source}</td>
                <td className="py-1">{pct(f.p)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {c.violations.length > 0 && (
        <section>
          <h2 className="mb-2 font-semibold">Violations</h2>
          <ul className="space-y-2 text-sm">
            {c.violations.map((v) => (
              <li key={v.rule}>
                <span className="font-bold">{v.rule}</span> <span className={muted}>{v.layer}</span> {v.text}
                <div className={`text-xs ${muted}`}>because: {v.because.join(", ")}</div>
              </li>
            ))}
          </ul>
        </section>
      )}

      {c.fix === null ? (
        <p className="text-sm">No change you control makes this compliant.</p>
      ) : c.fix.length > 0 ? (
        <section>
          <h2 className="mb-2 font-semibold">Fix</h2>
          <ul className="list-disc pl-5 text-sm">
            {c.fix.map((s) => (
              <li key={s.fact}>{fixLine(s)}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {c.questions.length > 0 && (
        <section>
          <h2 className="mb-2 font-semibold">Questions</h2>
          <ol className="list-decimal pl-5 text-sm">
            {c.questions.map((q) => (
              <li key={q.fact}>
                {q.text}
                {q.options && <span className={muted}> ({q.options.join(" / ")})</span>}
              </li>
            ))}
          </ol>
        </section>
      )}
    </article>
  );
}
