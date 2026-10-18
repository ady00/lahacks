import { redirect } from "next/navigation";
import { post } from "@/lib/api";
import { requireUser } from "@/lib/session";
import type { Case } from "@/lib/types";

const input = "w-full rounded border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700";

// Native GET form: with `text` in the URL the page POSTs /check server-side as the signed-in employee and
// redirects to the case, so a refresh never creates a second case.
export default async function CheckPage({ searchParams }: PageProps<"/check">) {
  const user = await requireUser();
  const { text, amount } = await searchParams;
  if (typeof text === "string") {
    const c = await post<Case>("/check", {
      text,
      employee_id: user.employee_id,
      amount: typeof amount === "string" && amount !== "" ? Number(amount) : undefined,
    });
    redirect(`/cases/${c.case_id}`);
  }
  return (
    <form method="get" className="max-w-xl space-y-4">
      <h1 className="text-xl font-semibold">{`Can I buy this, ${user.name}?`}</h1>
      <label className="block text-sm">
        What are you buying, and why?
        <textarea name="text" required rows={3} className={input} defaultValue="Client dinner Thursday with Acme's CFO, about $48." />
      </label>
      <label className="block text-sm">
        Amount (optional; otherwise the first $… in the text)
        <input name="amount" type="number" step="0.01" min="0.01" className={input} />
      </label>
      <button type="submit" className="rounded bg-zinc-900 px-4 py-2 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900">
        Check
      </button>
    </form>
  );
}
