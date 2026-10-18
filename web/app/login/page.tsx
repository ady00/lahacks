import { get } from "@/lib/api";
import { getUser } from "@/lib/session";
import type { EmployeeList } from "@/lib/types";
import { PageHeader } from "@/components/PageHeader";
import { btn, btnPrimary, card, h2, input } from "@/lib/ui";

const KINDS = [
  ["employee", "Employee"],
  ["intern", "Intern"],
  ["contractor", "Contractor"],
  ["manager", "Manager (approves purchases)"],
] as const;

// No passwords: a hackathon demo on two laptops. "manager" is a dashboard flag; the policy role stays employee.
export default async function LoginPage() {
  const [user, { employees }] = await Promise.all([getUser(), get<EmployeeList>("/employees")]);
  return (
    <div className="space-y-8">
      <PageHeader title="Sign in" text="No password. Your role decides which rules apply to your purchases." />
      {user && (
        <form method="post" action="/act/logout" className="flex items-center gap-3 text-sm">
          <span>
            You are signed in as <b>{user.name}</b>
            {user.manager && " (manager)"}.
          </span>
          <button className={btn}>Sign out</button>
        </form>
      )}
      <div className="grid gap-8 sm:grid-cols-2">
        <form method="post" action="/act/login" className={`${card} space-y-4 p-7`}>
          <h2 className={h2}>Existing employee</h2>
          <label className="block text-sm">
            <span className="font-medium">Who are you?</span>
            <select name="employee_id" className={`mt-1 ${input}`}>
              {employees.map((e) => (
                <option key={e.employee_id} value={e.employee_id}>
                  {`${e.name || "Unnamed"} · ${e.role} (${e.employee_id})`}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" name="manager" /> I approve purchases (shows the Approvals page)
          </label>
          <button className={btnPrimary}>Sign in</button>
        </form>

        <form method="post" action="/act/signup" className={`${card} space-y-4 p-7`}>
          <h2 className={h2}>New here</h2>
          <label className="block text-sm">
            <span className="font-medium">Your name</span>
            <input name="name" required className={`mt-1 ${input}`} />
          </label>
          <label className="block text-sm">
            <span className="font-medium">Your role</span>
            <select name="kind" className={`mt-1 ${input}`} defaultValue="employee">
              {KINDS.map(([v, label]) => (
                <option key={v} value={v}>{label}</option>
              ))}
            </select>
          </label>
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block text-sm">
              <span className="font-medium">Job title <span className="font-normal text-[#94A3B8]">(optional)</span></span>
              <input name="job_title" className={`mt-1 ${input}`} />
            </label>
            <label className="block text-sm">
              <span className="font-medium">Department <span className="font-normal text-[#94A3B8]">(optional)</span></span>
              <input name="department" className={`mt-1 ${input}`} />
            </label>
          </div>
          <label className="block text-sm">
            <span className="font-medium">Start date <span className="font-normal text-[#94A3B8]">(optional; blank means you started today)</span></span>
            <input name="start_date" type="date" className={`mt-1 ${input}`} />
          </label>
          <button className={btnPrimary}>Create account and sign in</button>
        </form>
      </div>
    </div>
  );
}
