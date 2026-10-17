import { get, post } from "@/lib/api";
import type { PolicyAudit, PolicyOut } from "@/lib/types";

const muted = "text-zinc-500 dark:text-zinc-400";

// The schema types rules and facts as plain dicts; these are the fields the contract documents.
type Rule = { id: string; layer: string; text: string; when?: unknown; require?: unknown };
type FactDef = { kind: string; values?: string[]; mutable?: boolean };

const kv = (o: Record<string, unknown>) =>
  Object.entries(o).map(([k, v]) => `${k}=${String(v)}`).join(", ");

export default async function RulesPage() {
  const [policy, audit] = await Promise.all([get<PolicyOut>("/policy"), post<PolicyAudit>("/policy/audit")]);
  const rules = policy.rules as Rule[];
  const facts = policy.facts as Record<string, FactDef>;
  return (
    <div className="space-y-8">
      <p className={`text-sm ${muted}`}>{`Policy version ${policy.version}`}</p>

      <section>
        <h1 className="mb-3 font-semibold">{`Rules (${rules.length})`}</h1>
        <div className="divide-y divide-zinc-100 dark:divide-zinc-800">
          {rules.map((r) => (
            <div key={r.id} className="grid grid-cols-[6rem_1fr_1fr] gap-4 py-3 text-sm">
              <div>
                <div className="font-bold">{r.id}</div>
                <div className={`text-xs ${muted}`}>{r.layer}</div>
              </div>
              <p>{r.text}</p>
              <pre className={`overflow-x-auto text-xs ${muted}`}>
                {JSON.stringify({ when: r.when, require: r.require }, null, 1)}
              </pre>
            </div>
          ))}
        </div>
      </section>

      <section className="space-y-2 text-sm">
        <h2 className="font-semibold">Policy audit</h2>
        <p>
          <span className={muted}>Dead rules: </span>
          {audit.dead.length ? audit.dead.join(", ") : "none"}
        </p>
        <div>
          <span className={muted}>Conflicts: </span>
          {audit.conflicts.length ? (
            <ul className="list-disc pl-5">
              {audit.conflicts.map((c) => (
                <li key={`${c.a}-${c.b}`}>
                  <span className="font-bold">{c.a}</span> × <span className="font-bold">{c.b}</span>
                  <span className={muted}> — e.g. {kv(c.example)}</span>
                </li>
              ))}
            </ul>
          ) : (
            "none"
          )}
        </div>
      </section>

      <section>
        <h2 className="mb-2 font-semibold">Facts</h2>
        <table className="w-full text-sm">
          <thead className={`text-left ${muted}`}>
            <tr>
              <th className="py-1 font-normal">Fact</th>
              <th className="py-1 font-normal">Kind</th>
              <th className="py-1 font-normal">Values</th>
              <th className="py-1 font-normal">Mutable</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(facts).map(([name, f]) => (
              <tr key={name} className="border-t border-zinc-100 dark:border-zinc-800">
                <td className="py-1 font-mono">{name}</td>
                <td className="py-1">{f.kind}</td>
                <td className={`py-1 ${muted}`}>{f.values?.join(", ")}</td>
                <td className="py-1">{String(f.mutable ?? "")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
