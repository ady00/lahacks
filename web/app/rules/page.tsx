import { detail, get, post } from "@/lib/api";
import type { PolicyAudit, PolicyOut, Rule, RuleDraft } from "@/lib/types";
import { expr, factLabel, requireText, valueText } from "@/lib/format";
import { PageHeader } from "@/components/PageHeader";
import { RuleRow } from "@/components/RuleRow";
import { Bolt, Chevron, Sparkle, Wand } from "@/components/icons";
import { btn, btnPrimary, card, chip, eyebrow, h2, mono, muted } from "@/lib/ui";

type FactDef = { kind: string; values?: string[]; mutable?: boolean };

const EXAMPLES = ["Hotels over $300 a night need a receipt", "Interns cannot expense software", "Client meals over $200 need manager approval"];

const kv = (o: Record<string, unknown>) =>
  Object.entries(o).map(([k, v]) => `${factLabel(k)} = ${valueText(k, v)}`).join(", ");

// Adding a rule is two native forms. GET ?text= asks the API to translate the sentence (Claude Code on the API host)
// and Z3-check it; nothing is saved. POST /act/rule-add saves exactly the drafted when/require and swaps the live policy.
export default async function RulesPage({ searchParams }: PageProps<"/rules">) {
  const { text } = await searchParams;
  const sentence = typeof text === "string" ? text.trim() : "";
  const [policy, audit, drafted] = await Promise.all([
    get<PolicyOut>("/policy"),
    post<PolicyAudit>("/policy/audit"),
    sentence ? post<RuleDraft>("/policy/rules/draft", { text: sentence }).then((d) => ({ d }), (e) => ({ err: detail(e) })) : null,
  ]);
  const rules = policy.rules as Rule[];
  const facts = policy.facts as Record<string, FactDef>;
  const draft = drafted && "d" in drafted ? drafted.d : null;
  const draftError = drafted && "err" in drafted ? drafted.err : null;
  const problems = draft ? (draft.dead ? 1 : 0) + draft.conflicts.length : 0;
  return (
    <>
      <PageHeader title="Policy Studio" text="Write a policy in plain English. Claude turns it into a rule, Z3 proves it fits the others, and the next check runs against it.">
        <span className="flex items-center gap-1.5 rounded-full bg-white px-3 py-1 shadow-[0_2px_3px_#00000033]">
          <span className={`size-1.75 rounded-full ${audit.conflicts.length || audit.dead.length ? "bg-amber-500" : "bg-secondary"}`} />
          <span className="font-serif text-[11.5px] font-semibold text-ink">
            {audit.conflicts.length || audit.dead.length ? "Consistency problems found" : "Status: Consistent (Z3 proved)"}
          </span>
        </span>
      </PageHeader>

      <section className={card}>
        <form method="get" action="/rules" className="space-y-3.5 border-b border-[#F1F5F9] bg-gradient-to-b from-[#FAFAF9] to-white px-5 pb-5 pt-6 sm:px-7">
          <div className="flex items-center gap-2">
            <span className="flex size-5 items-center justify-center rounded-md bg-[#EEF2FF] text-secondary"><Sparkle /></span>
            <span className={eyebrow}>Policy command</span>
          </div>
          <label className="flex min-h-13 items-center gap-3.5 rounded-xl border-[1.5px] border-secondary bg-white px-4.5 py-2 shadow-[0_0_0_3px_color-mix(in_oklab,var(--color-secondary)_15%,transparent),0_2px_4px_#00000005]">
            <Wand />
            <input
              name="text"
              required
              defaultValue={sentence}
              placeholder="Require VP approval if an engineer buys SaaS or cloud tools over $1,000 a month"
              className="min-w-0 grow bg-transparent font-serif text-[15px] font-medium tracking-[-0.01em] text-ink placeholder:text-[#94A3B8] focus:outline-none"
            />
            <kbd className="hidden rounded-md border border-[#E2E8F0] bg-[#F8FAFC] px-2.5 py-1 font-sans text-[11px] font-semibold text-[#64748B] sm:block">⏎ to translate</kbd>
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[12px] font-medium text-[#94A3B8]">Suggested templates:</span>
            {EXAMPLES.map((e) => (
              <a key={e} href={`/rules?text=${encodeURIComponent(e)}`} className={chip}>{e}</a>
            ))}
          </div>
        </form>

        {draftError && (
          <p role="alert" className="border-b border-main bg-[#FEF2F2] px-5 py-3 text-sm text-[#991B1B] sm:px-7">{draftError}</p>
        )}

        {draft && (
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-main bg-[#FAFAFA] px-5 py-3 font-serif text-[12px] sm:px-7">
            <div className="flex flex-wrap items-center gap-2">
              <span className="mr-1 font-semibold text-[#64748B]">Tokens:</span>
              <Token label="When" value={expr(draft.rule.when)} />
              <Token label="Then" value={requireText(draft.rule.require)} />
            </div>
            <span className="flex items-center gap-1.5 rounded-full bg-white px-3 py-1 shadow-[0_2px_3px_#00000033]">
              <span className={`size-1.75 rounded-full ${problems ? "bg-amber-500" : "bg-secondary"}`} />
              <span className="text-[11.5px] font-semibold text-ink">
                {draft.dead ? "Status: Can never fire" : draft.conflicts.length ? `Status: Conflicts with ${draft.conflicts.map((c) => (c.a === draft.rule.id ? c.b : c.a)).join(", ")}` : "Status: Valid (Z3 proved)"}
              </span>
            </span>
          </div>
        )}
        {draft && draft.conflicts.length > 0 && (
          <ul className={`border-b border-main px-5 py-3 text-[12px] sm:px-7 ${muted}`}>
            {draft.conflicts.map((c) => (
              <li key={`${c.a}-${c.b}`}>{`Disagrees with rule ${c.a === draft.rule.id ? c.b : c.a} when ${kv(c.example)}`}</li>
            ))}
          </ul>
        )}

        <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3 sm:px-7">
          {draft ? (
            <>
              <div className="flex min-w-0 flex-wrap items-center gap-2.5">
                <span className="text-secondary"><Chevron /></span>
                <span className="font-serif text-[13.5px] font-semibold text-ink">{`Rule ${draft.rule.id}: ${draft.rule.text}`}</span>
                <span className={`${mono} text-[12.5px] text-[#64748B]`}>{`(${rules.length} rules checked · ${problems} ${problems === 1 ? "problem" : "problems"})`}</span>
              </div>
              <form method="post" action="/act/rule-add" className="flex items-center gap-3">
                <input type="hidden" name="text" value={draft.rule.text} />
                <input type="hidden" name="when" value={JSON.stringify(draft.rule.when ?? null)} />
                <input type="hidden" name="require" value={JSON.stringify(draft.rule.require ?? null)} />
                <a href="/rules" className={btn}>Discard</a>
                <button className={btnPrimary}><Bolt /> {problems ? "Save anyway" : "Save & Activate Policy"}</button>
              </form>
            </>
          ) : (
            <>
              <div className="flex items-center gap-2.5">
                <span className="text-secondary"><Chevron /></span>
                <span className="font-serif text-[13.5px] font-semibold text-ink">What happens next</span>
                <span className={`${mono} text-[12.5px] text-[#64748B]`}>{`(translate · Z3 check against ${rules.length} rules · activate)`}</span>
              </div>
              <p className={`text-[12px] ${muted}`}>Nothing is saved until you activate it.</p>
            </>
          )}
        </div>
      </section>

      <section className="mt-9 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className={h2}>{`Active verified rules (${rules.length})`}</h2>
          <span className={`text-[12px] ${muted}`}>{`Version ${policy.version}`}</span>
        </div>
        {rules.map((r) => (
          <RuleRow key={r.id} r={r} />
        ))}
      </section>

      <section className={`${card} mt-9 space-y-2 p-7 text-sm`}>
        <h2 className={h2}>Consistency check</h2>
        <p className={muted}>Z3 proves whether any rule can never fire and whether any two rules can disagree on the same purchase.</p>
        <p>
          <span className={muted}>Rules that can never fire: </span>
          {audit.dead.length ? audit.dead.join(", ") : "none"}
        </p>
        <div>
          <span className={muted}>Rules that conflict: </span>
          {audit.conflicts.length ? (
            <ul className="list-disc pl-5">
              {audit.conflicts.map((c) => (
                <li key={`${c.a}-${c.b}`}>
                  <span className="font-mono text-xs font-semibold">{c.a}</span> and <span className="font-mono text-xs font-semibold">{c.b}</span>
                  <span className={muted}>{` disagree when ${kv(c.example)}`}</span>
                </li>
              ))}
            </ul>
          ) : (
            "none"
          )}
        </div>
      </section>

      <section className={`${card} mt-6 p-7`}>
        <h2 className={h2}>Facts the rules can use</h2>
        <p className={`mb-3 mt-1 text-sm ${muted}`}>What a purchase is reduced to before Z3 sees it.</p>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className={`text-left ${muted}`}>
              <tr>
                <th className="py-1 pr-3 font-normal">Fact</th>
                <th className="py-1 pr-3 font-normal">Type</th>
                <th className="py-1 pr-3 font-normal">Allowed values</th>
                <th className="py-1 font-normal">Person can change it</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(facts).map(([name, f]) => (
                <tr key={name} className="border-t border-[#F1F5F9]">
                  <td className="py-1.5 pr-3">
                    {factLabel(name)} <span className="font-mono text-xs text-[#94A3B8]">{name}</span>
                  </td>
                  <td className="py-1.5 pr-3">{f.kind === "bool" ? "yes/no" : f.kind === "enum" ? "one of a list" : f.kind}</td>
                  <td className={`py-1.5 pr-3 ${muted}`}>{f.values?.join(", ")}</td>
                  <td className="py-1.5">{f.mutable == null ? "" : f.mutable ? "Yes" : "No"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
