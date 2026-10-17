import type { Case } from "@/lib/types";

const STYLE: Record<Case["verdict"], string> = {
  compliant: "bg-green-100 text-green-800",
  violation: "bg-red-100 text-red-800",
  undetermined: "bg-amber-100 text-amber-800",
};

export function VerdictChip({ verdict }: { verdict: Case["verdict"] }) {
  return <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STYLE[verdict]}`}>{verdict}</span>;
}
