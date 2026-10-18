import type { Case } from "@/lib/types";

const STYLE: Record<Case["verdict"], string> = {
  compliant: "bg-[#F0FDF4] text-[#16A34A] border border-[#DCFCE7]",
  violation: "bg-[#FEF2F2] text-[#DC2626] border border-[#FEE2E2]",
  undetermined: "bg-[#FFFBEB] text-[#D97706] border border-[#FEF3C7]",
};

const DOT_STYLE: Record<Case["verdict"], string> = {
  compliant: "bg-[#16A34A]",
  violation: "bg-[#DC2626]",
  undetermined: "bg-[#D97706]",
};

// The solver's word stays visible in a tooltip; the chip says what it means.
export const VERDICT_TEXT: Record<Case["verdict"], string> = {
  compliant: "Allowed",
  violation: "Not allowed",
  undetermined: "Needs a detail",
};

export function VerdictChip({ verdict }: { verdict: Case["verdict"] }) {
  return (
    <span
      title={`Z3 verdict: ${verdict}`}
      className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-0.5 text-[11px] font-semibold shadow-[0_1px_2px_rgba(0,0,0,0.04)] transition-all duration-150 hover:scale-[1.03] ${STYLE[verdict]}`}
    >
      <span className="relative flex size-1.5">
        {verdict === "compliant" && (
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#16A34A] opacity-75" />
        )}
        <span className={`relative inline-flex size-1.5 rounded-full ${DOT_STYLE[verdict]}`} />
      </span>
      {VERDICT_TEXT[verdict]}
    </span>
  );
}
