import { detail, post } from "@/lib/api";
import { DEFAULT_RULES, parseBankRules } from "@/lib/bankrules";
import { usd } from "@/lib/format";
import type { BankRulesOut } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { Bolt } from "@/components/icons";
import { btnPrimary, card, eyebrow, h2, input, muted } from "@/lib/ui";

const range = (min?: number | null, max?: number | null) =>
  min == null && max == null ? "any amount" : `${min == null ? "any" : usd(min)} to ${max == null ? "any" : usd(max)}`;

const example = (ex: Record<string, unknown>) => {
  const amount = typeof ex.amount === "number" ? `a ${usd(ex.amount)} charge` : "a charge";
  return typeof ex.description === "string" ? `${amount} described “${ex.description}…”` : amount;
};

// Same shape as Policy Studio: a native GET form; the server parses the lines and asks Z3. With no ?rules= the
// default set runs so the page is never empty.
export default async function BankRulesPage({ searchParams }: PageProps<"/bank-rules">) {
  const { rules: raw } = await searchParams;
  const text = typeof raw === "string" && raw.trim() ? raw : DEFAULT_RULES;
  const { rules, errors } = parseBankRules(text);
  const checked = errors.length || !rules.length ? null : await post<BankRulesOut>("/bank-rules/check", { rules }).then((d) => ({ d }), (e) => ({ err: detail(e) }));
  const out = checked && "d" in checked ? checked.d : null;
  const apiError = checked && "err" in checked ? checked.err : null;
  // ponytail: a shadowed pair is trivially an overlap too; the shadow section already explains it
  const overlaps = out?.overlaps.filter((o) => !out.shadowed.some((s) => (s.rule === o.a && s.by.includes(o.b)) || (s.rule === o.b && s.by.includes(o.a)))) ?? [];
  const problems = (out?.shadowed.length ?? 0) + overlaps.length;
  return (
    <>
      <PageHeader title="Bank rules" text="Paste your QuickBooks bank rules. Z3 finds the ones that can never fire and the pairs that overlap.">
        {out && (
          <span className="flex items-center gap-1.5 rounded-full bg-white px-3 py-1 shadow-[0_2px_3px_#00000033]">
            <span className={`size-1.75 rounded-full ${problems ? "bg-amber-500" : "bg-secondary"}`} />
            <span className="font-serif text-[11.5px] font-semibold text-ink">
              {problems ? `${problems} ${problems === 1 ? "problem" : "problems"} found` : "No shadowed or overlapping rules (Z3 proved)"}
            </span>
          </span>
        )}
      </PageHeader>

      <section className={card}>
        <form method="get" action="/bank-rules" className="space-y-3.5 border-b border-[#F1F5F9] bg-gradient-to-b from-[#FAFAF9] to-white px-5 pb-5 pt-6 sm:px-7">
          <p className={eyebrow}>Your rules, in order</p>
          <textarea name="rules" rows={9} defaultValue={text} spellCheck={false} className={`${input} font-mono text-[13px]`} />
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className={`text-[12px] ${muted}`}>One rule per line: id | words the description contains | min | max | category. Leave min or max blank for no limit.</p>
            <button className={btnPrimary}><Bolt /> Check with Z3</button>
          </div>
        </form>
        {errors.length > 0 && (
          <ul role="alert" className="space-y-0.5 border-b border-main bg-[#FEF2F2] px-5 py-3 text-sm text-[#991B1B] sm:px-7">
            {errors.map((e) => <li key={e}>{e}</li>)}
          </ul>
        )}
        {apiError && <p role="alert" className="border-b border-main bg-[#FEF2F2] px-5 py-3 text-sm text-[#991B1B] sm:px-7">{apiError}</p>}
        <div className="overflow-x-auto px-5 py-3 sm:px-7">
          <table className="w-full text-sm">
            <thead className={`text-left ${muted}`}>
              <tr>
                <th className="py-1 pr-3 font-normal">#</th>
                <th className="py-1 pr-3 font-normal">Rule</th>
                <th className="py-1 pr-3 font-normal">Description contains</th>
                <th className="py-1 pr-3 font-normal">Amount</th>
                <th className="py-1 font-normal">Category</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((r, i) => (
                <tr key={r.id} className="border-t border-[#F1F5F9]">
                  <td className={`py-1.5 pr-3 ${muted}`}>{i + 1}</td>
                  <td className="py-1.5 pr-3 font-mono text-xs font-semibold">{r.id}</td>
                  <td className="py-1.5 pr-3">{r.contains.length ? r.contains.join(" ") : <span className={muted}>any description</span>}</td>
                  <td className="py-1.5 pr-3">{range(r.amount_min, r.amount_max)}</td>
                  <td className="py-1.5">{r.category}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {out && (
        <>
          <section className={`${card} mt-9 space-y-2 p-7 text-sm`}>
            <h2 className={h2}>Rules that can never fire</h2>
            <p className={muted}>An earlier rule always catches their transactions first.</p>
            {out.shadowed.length ? (
              <ul className="list-disc pl-5">
                {out.shadowed.map((s) => (
                  <li key={s.rule}>
                    <span className="font-mono text-xs font-semibold">{s.rule}</span>
                    <span className={muted}>{` is shadowed by `}</span>
                    <span className="font-mono text-xs font-semibold">{s.by.join(", ")}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p>None. Every rule has a transaction only it matches first.</p>
            )}
          </section>

          <section className={`${card} mt-6 space-y-2 p-7 text-sm`}>
            <h2 className={h2}>Rules that overlap</h2>
            <p className={muted}>Same transaction, different categories.</p>
            {overlaps.length ? (
              <ul className="list-disc pl-5">
                {overlaps.map((o) => (
                  <li key={`${o.a}-${o.b}`}>
                    {`${example(o.example)} matches both `}
                    <span className="font-mono text-xs font-semibold">{o.a}</span>
                    {" and "}
                    <span className="font-mono text-xs font-semibold">{o.b}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p>None.</p>
            )}
          </section>
        </>
      )}
    </>
  );
}
