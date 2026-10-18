import { redirect } from "next/navigation";
import { post } from "@/lib/api";
import { requireUser } from "@/lib/session";
import type { Case } from "@/lib/types";

// The home page's form lands here: with `text` in the URL this POSTs /check server-side as the signed-in
// employee and redirects to the case, so a refresh never creates a second case. Without it, go home.
export default async function CheckPage({ searchParams }: PageProps<"/check">) {
  const user = await requireUser();
  const { text, amount } = await searchParams;
  if (typeof text !== "string" || text.trim() === "") redirect("/");
  const c = await post<Case>("/check", {
    text,
    employee_id: user.employee_id,
    amount: typeof amount === "string" && amount !== "" ? Number(amount) : undefined,
  });
  redirect(`/cases/${c.case_id}`);
}
