import { NextResponse } from "next/server";
import { del, get, post } from "@/lib/api";
import { COOKIE, cookieOptions, getUser, type User } from "@/lib/session";
import type { Employee, EmployeeList } from "@/lib/types";

// Every dashboard mutation is a native <form method="post" action="/act/<name>"> to this handler:
// no client JS, curl-testable, and the API error (404/409/422) surfaces as a thrown Error (Next → 500 + log).
const str = (f: FormData, k: string) => String(f.get(k) ?? "");
const answerValue = (f: FormData) => {
  const raw = str(f, "value");
  return raw === "true" ? true : raw === "false" ? false : raw !== "" && !isNaN(Number(raw)) ? Number(raw) : raw;
};

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
      const optional = Object.fromEntries(["job_title", "department", "start_date"].map((k) => [k, str(f, k)]).filter(([, v]) => v));
      const e = await post<Employee>("/employees", {
        name: str(f, "name"),
        role: manager ? "employee" : kind,
        manager_id: manager ? "" : "e_manager",
        ...optional, // blank ones stay out so the API's defaults apply (start_date = today)
      });
      return redirectTo(req, "/", { employee_id: e.employee_id, name: e.name, manager });
    }
    case "login": {
      const id = str(f, "employee_id");
      const row = (await get<EmployeeList>("/employees")).employees.find((e) => e.employee_id === id);
      if (!row) throw new Error(`unknown employee ${id}`);
      return redirectTo(req, "/", { employee_id: row.employee_id, name: row.name, manager: str(f, "manager") === "on" });
    }
    case "rule-add": {
      // the draft's when/require come back exactly as the API drafted them, as JSON in hidden fields
      await post("/policy/rules", { text: str(f, "text"), when: JSON.parse(str(f, "when")), require: JSON.parse(str(f, "require")) });
      return redirectTo(req, "/rules");
    }
    case "irs-layer": {
      await post("/policy/layers", { irs: str(f, "irs") === "true" });
      return redirectTo(req, "/irs");
    }
    case "rule-delete": {
      await del(`/policy/rules/${encodeURIComponent(str(f, "rule_id"))}`);
      return redirectTo(req, "/rules");
    }
    case "logout":
      return redirectTo(req, "/login", null);
    case "answer": {
      const id = str(f, "case_id");
      await post(`/cases/${id}/answer`, { fact: str(f, "fact"), value: answerValue(f) });
      return redirectTo(req, `/cases/${id}`);
    }
    case "ledger-answer": {
      await post(`/ledger/${encodeURIComponent(str(f, "txn_id"))}/answer`, { fact: str(f, "fact"), value: answerValue(f) });
      return redirectTo(req, "/ledger");
    }
    case "authorize": {
      const id = str(f, "case_id");
      await post(`/cases/${id}/authorize`);
      return redirectTo(req, `/cases/${id}`);
    }
    case "approve": {
      const user = await getUser();
      if (!user?.manager) return new Response("managers only", { status: 403 });
      await post(`/cases/${str(f, "case_id")}/approve`, { approver: user.employee_id, approved: str(f, "approved") === "true" });
      return redirectTo(req, "/approvals");
    }
    default:
      return new Response("unknown action", { status: 404 });
  }
}
