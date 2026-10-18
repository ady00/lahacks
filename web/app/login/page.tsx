import { get } from "@/lib/api";
import { getUser } from "@/lib/session";
import type { EmployeeList } from "@/lib/types";
import { btn, btnPrimary, h1, input } from "@/lib/ui";

const KINDS = ["employee", "intern", "contractor", "manager"];

// No passwords: a hackathon demo on two laptops. "manager" is a dashboard flag; the policy role stays employee.
export default async function LoginPage() {
  const [user, { employees }] = await Promise.all([getUser(), get<EmployeeList>("/employees")]);
  return (
    <div className="space-y-8">
      <h1 className={h1}>Sign in</h1>
      {user && (
        <form method="post" action="/act/logout" className="flex items-center gap-3 text-sm">
          <span>
            Signed in as <b>{user.name}</b>
            {user.manager && " (manager)"}
          </span>
          <button className={btn}>Sign out</button>
        </form>
      )}
      <div className="grid gap-8 sm:grid-cols-2">
        <form method="post" action="/act/signup" className="space-y-4">
          <h2 className="font-semibold">Sign up</h2>
          <label className="block text-sm">
            Your name
            <input name="name" required className={input} />
          </label>
          <label className="block text-sm">
            You are a…
            <select name="kind" className={input} defaultValue="employee">
              {KINDS.map((k) => (
                <option key={k}>{k}</option>
              ))}
            </select>
          </label>
          <button className={btnPrimary}>Create account</button>
        </form>

        <form method="post" action="/act/login" className="space-y-4">
          <h2 className="font-semibold">Sign in as</h2>
          <label className="block text-sm">
            Existing employee
            <select name="employee_id" className={input}>
              {employees.map((e) => (
                <option key={e.employee_id} value={e.employee_id}>
                  {`${e.name} (${e.employee_id})`}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" name="manager" /> I approve purchases
          </label>
          <button className={btnPrimary}>Sign in</button>
        </form>
      </div>
    </div>
  );
}
