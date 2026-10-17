import { get } from "@/lib/api";
import type { Case } from "@/lib/types";
import { CaseCard } from "@/components/CaseCard";

export default async function CasePage({ params }: PageProps<"/cases/[id]">) {
  const { id } = await params;
  const c = await get<Case>(`/cases/${id}`);
  return <CaseCard c={c} />;
}
