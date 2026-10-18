// Dashboard identity: one httpOnly cookie, read only here. The API has no auth; it only needs employee_id.
export type User = { employee_id: string; name: string; manager: boolean };

export const COOKIE = "pop_user";

export const cookieOptions = () => ({ httpOnly: true, sameSite: "lax" as const, path: "/", maxAge: 2592000 });

/** Pure, so `node --test` covers it without loading Next. Anything but the exact shape is "signed out". */
export function parseUser(raw: string | undefined): User | null {
  if (!raw) return null;
  try {
    const u = JSON.parse(raw);
    return typeof u?.employee_id === "string" && typeof u.name === "string" && typeof u.manager === "boolean"
      ? { employee_id: u.employee_id, name: u.name, manager: u.manager }
      : null;
  } catch {
    return null;
  }
}

export async function getUser(): Promise<User | null> {
  const { cookies } = await import("next/headers"); // lazy so the pure part stays importable outside Next
  return parseUser((await cookies()).get(COOKIE)?.value);
}

export async function requireUser(): Promise<User> {
  const user = await getUser();
  if (user) return user;
  const { redirect } = await import("next/navigation");
  return redirect("/login"); // `never`; the explicit return is what lets TS see the function always yields a User
}
