import { get } from "@/lib/api";
import type { EvalOut } from "@/lib/types";
import { pct, usd, when } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { card, muted } from "@/lib/ui";

const HEAD = ["System", "Verdict accuracy", "Cites the right rules (F1)", "Same answer on rerun", "Median latency", "Cost per 1,000 checks", "Questions asked per check"];

export default async function EvalPage() {
  const { as_of, n_heldout, systems } = await get<EvalOut>("/eval");
  return (
    <div className="animate-fade-in-up space-y-4">
      <PageHeader
        title="Evaluation"
        text="Each system judged the same held-out transactions against labels a person wrote from the policy. Higher is better except latency and cost."
      />
      {systems.length === 0 ? (
        <p className={muted}>No results yet. This fills in once the evaluation run writes its results file.</p>
      ) : (
        <>
          <p className={`text-sm ${muted}`}>{`${n_heldout} held-out transactions · run ${as_of ? when(as_of) : "at an unknown time"}`}</p>
          <div className="overflow-x-auto rounded-lg border border-[#F1F5F9]">
            <table className={`${card} w-full text-sm`}>
            <thead className={`bg-[#F8FAFC] text-left ${muted}`}>
              <tr>
                {HEAD.map((h) => (
                  <th key={h} className="px-3.5 py-2.5 font-medium first:pl-5">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {systems.map((s) => {
                const isHero = s.name === "Jev + Z3";
                return (
                  <tr
                    key={s.name}
                    className={`border-t border-[#F1F5F9] tabular-nums transition-colors duration-150 ${
                      isHero
                        ? "bg-gradient-to-r from-[#F0FDF4] via-[#ECFDF5] to-white font-semibold text-emerald-950 shadow-2xs"
                        : "hover:bg-[#F8FAFC]"
                    }`}
                  >
                    <td className="px-3.5 py-3 first:pl-5">
                      <div className="flex items-center gap-2">
                        <span>{s.name}</span>
                        {isHero && (
                          <span className="inline-flex items-center gap-1 rounded-full border border-emerald-300 bg-emerald-100/90 px-2 py-0.5 text-[10.5px] font-semibold text-emerald-800 shadow-2xs">
                            <span className="size-1.5 rounded-full bg-emerald-600 animate-pulse" />
                            this product
                          </span>
                        )}
                      </div>
                    </td>
                    <td className={`px-3.5 py-3 first:pl-5 ${isHero ? "text-emerald-700" : ""}`}>{pct(s.accuracy)}</td>
                    <td className={`px-3.5 py-3 first:pl-5 ${isHero ? "text-emerald-700" : ""}`}>{pct(s.citation_f1)}</td>
                    <td className={`px-3.5 py-3 first:pl-5 ${isHero ? "text-emerald-700" : ""}`}>{pct(s.rerun_agreement)}</td>
                    <td className="px-3.5 py-3 first:pl-5">{`${Math.round(s.median_latency_ms)} ms`}</td>
                    <td className="px-3.5 py-3 first:pl-5">{usd(s.cost_per_1k_usd)}</td>
                    <td className="px-3.5 py-3">{s.questions_per_txn.toFixed(2)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        </>
      )}
    </div>
  );
}
