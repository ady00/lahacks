import type { Case } from "@/lib/types";

const STYLE: Record<Case["verdict"], string> = {
  compliant: "bg-[#F0FDF4] text-[#16A34A]",
  violation: "bg-[#FEF2F2] text-[#DC2626]",
  undetermined: "bg-[#FFFBEB] text-[#D97706]",
};
// The solver's word stays visible in a tooltip; the chip says what it means.
export const VERDICT_TEXT: Record<Case["verdict"], string> = {
  compliant: "Allowed",
  violation: "Not allowed",
  undetermined: "Needs a detail",
};

export function VerdictChip({ verdict }: { verdict: Case["verdict"] }) {
  return (
    <span title={`Z3 verdict: ${verdict}`} className={`rounded px-2 py-0.5 text-[11px] font-semibold ${STYLE[verdict]}`}>
      {VERDICT_TEXT[verdict]}
    </span>
  );
}
