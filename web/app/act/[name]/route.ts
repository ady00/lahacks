import { NextResponse } from "next/server";
import { get, post } from "@/lib/api";
import { COOKIE, cookieOptions, type User } from "@/lib/session";
import type { Employee, EmployeeList } from "@/lib/types";

// Every dashboard mutation is a native <form method="post" action="/act/<name>"> to this handler:
// no client JS, curl-testable, and the API error (404/409/422) surfaces as a thrown Error (Next → 500 + log).
const str = (f: FormData, k: string) => String(f.get(k) ?? "");

function redirectTo(req: Request, path: string, user?: User | null) {
  const res = NextResponse.redirect(new URL(path, req.url), 303);
  if (user) res.cookies.set(COOKIE, JSON.stringify(user), cookieOptions());
  if (user === null) res.cookies.set(COOKIE, "", { ...cookieOptions(), maxAge: 0 });
  return res;
}

export async function POST(req: Request, ctx: RouteContext<"/act/[name]">) {
  const { name } = await ctx.params;
  const f = await req.formData().catch(() => new FormData()); // a body-less POST (curl, a bare fetch) is just "no fields"
  switch (name) {
    case "signup": {
      const kind = str(f, "kind");
      const manager = kind === "manager";
      const e = await post<Employee>("/employees", {
        name: str(f, "name"),
        role: manager ? "employee" : kind,
        manager_id: manager ? "" : "e_manager",
      });
      return redirectTo(req, "/check", { employee_id: e.employee_id, name: e.name, manager });
    }
    case "login": {
      const id = str(f, "employee_id");
      const row = (await get<EmployeeList>("/employees")).employees.find((e) => e.employee_id === id);
      if (!row) throw new Error(`unknown employee ${id}`);
      return redirectTo(req, "/check", { employee_id: row.employee_id, name: row.name, manager: str(f, "manager") === "on" });
    }
    case "logout":
      return redirectTo(req, "/login", null);
    default:
      return new Response("unknown action", { status: 404 });
  }
}
