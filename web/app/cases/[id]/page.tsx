import { get } from "@/lib/api";
import { requireUser } from "@/lib/session";
import type { Case } from "@/lib/types";
import { CaseCard } from "@/components/CaseCard";

const btn = "rounded border border-zinc-300 px-3 py-1.5 text-sm hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800";
const btnPrimary = "rounded bg-zinc-900 px-4 py-2 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900";

// Every button is a native form to /act/<verb>; the API re-proves and this page re-renders whatever it says.
export default async function CasePage({ params }: PageProps<"/cases/[id]">) {
  await requireUser();
  const { id } = await params;
  const c = await get<Case>(`/cases/${id}`);
  const q = c.questions[0];
  const choices = q ? (q.options ?? ["true", "false"]) : [];
  return (
    <div className="space-y-6">
      {c.awaiting_approval && <meta httpEquiv="refresh" content="5" />}
      <CaseCard c={c} />

      {q && (
        <section className="space-y-2">
          <h2 className="font-semibold">{q.text}</h2>
          <div className="flex flex-wrap gap-2">
            {choices.map((v) => (
              <form key={v} method="post" action="/act/answer">
                <input type="hidden" name="case_id" value={c.case_id} />
                <input type="hidden" name="fact" value={q.fact} />
                <input type="hidden" name="value" value={v} />
                <button className={btn}>{q.options ? v : v === "true" ? "Yes" : "No"}</button>
              </form>
            ))}
          </div>
        </section>
      )}

      {c.verdict === "compliant" && !c.authorization && (
        <form method="post" action="/act/authorize">
          <input type="hidden" name="case_id" value={c.case_id} />
          <button className={btnPrimary}>Authorize card</button>
        </form>
      )}
    </div>
  );
}
