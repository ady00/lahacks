import { get } from "@/lib/api";
import { getUser } from "@/lib/session";
import type { EmployeeList } from "@/lib/types";

const KINDS = ["employee", "intern", "contractor", "manager"];
const input = "w-full rounded border border-zinc-300 bg-transparent px-3 py-2 dark:border-zinc-700";
const button = "rounded bg-zinc-900 px-4 py-2 text-sm font-medium text-white dark:bg-zinc-100 dark:text-zinc-900";

// No passwords: a hackathon demo on two laptops. "manager" is a dashboard flag; the policy role stays employee.
export default async function LoginPage() {
  const [user, { employees }] = await Promise.all([getUser(), get<EmployeeList>("/employees")]);
  return (
    <div className="space-y-8">
      <h1 className="text-xl font-semibold">Sign in</h1>
      {user && (
        <form method="post" action="/act/logout" className="flex items-center gap-3 text-sm">
          <span>
            Signed in as <b>{user.name}</b>
            {user.manager && " (manager)"}
          </span>
          <button className="rounded border px-3 py-1">Sign out</button>
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
          <button className={button}>Create account</button>
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
          <button className={button}>Sign in</button>
        </form>
      </div>
    </div>
  );
}
