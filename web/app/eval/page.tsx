import { get } from "@/lib/api";
import type { EvalOut } from "@/lib/types";
import { pct, usd } from "@/lib/format";

const muted = "text-zinc-500 dark:text-zinc-400";
const HEAD = ["System", "Accuracy", "Citation F1", "Rerun agreement", "Median latency (ms)", "Cost / 1k (USD)", "Questions / txn"];

export default async function EvalPage() {
  const { as_of, n_heldout, systems } = await get<EvalOut>("/eval");
  if (systems.length === 0) return <p className={muted}>No evaluation results yet.</p>;
  return (
    <div className="space-y-4">
      <p className={`text-sm ${muted}`}>{`As of ${as_of} · ${n_heldout} held-out transactions`}</p>
      <table className="w-full text-sm">
        <thead className={`text-left ${muted}`}>
          <tr>
            {HEAD.map((h) => (
              <th key={h} className="py-1 pr-3 font-normal">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {systems.map((s) => (
            <tr
              key={s.name}
              className={`border-t border-zinc-100 dark:border-zinc-800 ${s.name === "Jev + Z3" ? "font-semibold bg-green-50 dark:bg-green-950" : ""}`}
            >
              <td className="py-1 pr-3">{s.name}</td>
              <td className="py-1 pr-3">{pct(s.accuracy)}</td>
              <td className="py-1 pr-3">{pct(s.citation_f1)}</td>
              <td className="py-1 pr-3">{pct(s.rerun_agreement)}</td>
              <td className="py-1 pr-3">{Math.round(s.median_latency_ms)}</td>
              <td className="py-1 pr-3">{usd(s.cost_per_1k_usd)}</td>
              <td className="py-1">{s.questions_per_txn.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
