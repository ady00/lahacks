import { get } from "@/lib/api";
import type { EvalOut } from "@/lib/types";
import { pct, usd, when } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { card, muted } from "@/lib/ui";

const HEAD = ["System", "Verdict accuracy", "Cites the right rules (F1)", "Same answer on rerun", "Median latency", "Cost per 1,000 checks", "Questions asked per check"];

export default async function EvalPage() {
  const { as_of, n_heldout, systems } = await get<EvalOut>("/eval");
  return (
    <div className="space-y-4">
      <PageHeader
        title="Evaluation"
        text="Each system judged the same held-out transactions against labels a person wrote from the policy. Higher is better except latency and cost."
      />
      {systems.length === 0 ? (
        <p className={muted}>No results yet. This fills in once the evaluation run writes its results file.</p>
      ) : (
        <>
          <p className={`text-sm ${muted}`}>{`${n_heldout} held-out transactions · run ${as_of ? when(as_of) : "at an unknown time"}`}</p>
          <div className="overflow-x-auto">
            <table className={`${card} w-full text-sm`}>
            <thead className={`text-left ${muted}`}>
              <tr>
                {HEAD.map((h) => (
                  <th key={h} className="px-3 py-2 font-normal first:pl-5">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {systems.map((s) => (
                <tr
                  key={s.name}
                  className={`border-t border-[#F1F5F9] tabular-nums ${s.name === "Jev + Z3" ? "bg-[#F0FDF4] font-semibold" : ""}`}
                >
                  <td className="px-3 py-2 first:pl-5">{s.name}{s.name === "Jev + Z3" && <span className={`ml-2 text-xs font-normal ${muted}`}>this product</span>}</td>
                  <td className="px-3 py-2 first:pl-5">{pct(s.accuracy)}</td>
                  <td className="px-3 py-2 first:pl-5">{pct(s.citation_f1)}</td>
                  <td className="px-3 py-2 first:pl-5">{pct(s.rerun_agreement)}</td>
                  <td className="px-3 py-2 first:pl-5">{`${Math.round(s.median_latency_ms)} ms`}</td>
                  <td className="px-3 py-2 first:pl-5">{usd(s.cost_per_1k_usd)}</td>
                  <td className="px-3 py-2">{s.questions_per_txn.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        </>
      )}
    </div>
  );
}
