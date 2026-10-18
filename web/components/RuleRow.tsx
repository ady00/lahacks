import { expr, requireText } from "@/lib/format";
import type { Rule } from "@/lib/types";
import { mono, row } from "@/lib/ui";

export type { Rule };

const LAYER: Record<string, [string, string]> = { company: ["Company", "text-[#6366F1]"], irs: ["Statutory", "text-[#0D9488]"] };
const CUSTOM: [string, string] = ["Added here", "text-secondary"];

/** One policy rule as the Paper design draws it: id and layer, the sentence, the logic in mono, a live chip. */
export function RuleRow({ r }: { r: Rule }) {
  const [layer, color] = r.custom ? CUSTOM : LAYER[r.layer] ?? [r.layer, "text-[#64748B]"];
  return (
    <div className={`${row} group flex flex-wrap items-center justify-between gap-3 transition-all duration-200 hover:border-[#CBD5E1] hover:shadow-[0_4px_14px_rgba(15,23,42,0.06)]`}>
      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-x-5 gap-y-1 sm:flex-nowrap">
        <div className="w-20 shrink-0">
          <div className="font-serif text-[13px] font-bold text-ink transition-colors group-hover:text-secondary">{`Rule ${r.id}`}</div>
          <div className={`text-[11px] font-medium ${color}`}>{layer}</div>
        </div>
        <div className="min-w-0">
          <p className="text-[13px] font-medium text-[#1E293B]">{r.text}</p>
          <p className={`${mono} break-words transition-colors group-hover:text-[#64748B] sm:truncate`}>{`when: ${expr(r.when)}  |  ${requireText(r.require).toLowerCase()}`}</p>
        </div>
      </div>
      <div className="flex items-center gap-2.5">
        <span className="inline-flex items-center gap-1.5 rounded-md border border-[#DCFCE7] bg-[#F0FDF4] px-2 py-0.5 text-[11px] font-semibold text-[#16A34A] shadow-[0_1px_2px_rgba(0,0,0,0.03)]">
          <span className="relative flex size-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#16A34A] opacity-75" />
            <span className="relative inline-flex size-1.5 rounded-full bg-[#16A34A]" />
          </span>
          Live Active
        </span>
        {r.custom && (
          <form method="post" action="/act/rule-delete">
            <input type="hidden" name="rule_id" value={r.id} />
            <button className="rounded-md border border-[#E2E8F0] bg-white px-2 py-1 text-[11px] font-medium text-[#64748B] transition-all duration-150 hover:border-[#DC2626] hover:bg-[#FEF2F2] hover:text-[#DC2626] active:scale-95">Remove</button>
          </form>
        )}
      </div>
    </div>
  );
}
