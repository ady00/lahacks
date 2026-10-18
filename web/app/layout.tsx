import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import { API_URL, get } from "@/lib/api";
import { getUser } from "@/lib/session";
import type { Health } from "@/lib/types";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Proof of Purchase",
  description: "Purchase checks proven by Z3",
};

const NAV = [
  ["Check", "/check"],
  ["Ledger", "/ledger"],
  ["Rules", "/rules"],
  ["Evaluation", "/eval"],
] as const;
const link = "text-sm text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100";
const chip = "rounded px-2 py-0.5 text-xs font-medium";

export default async function RootLayout({ children }: LayoutProps<"/">) {
  let stub = false;
  let down = false;
  try {
    stub = (await get<Health>("/health")).stub;
  } catch {
    down = true; // server-rendered, so the message survives production (error.tsx only gets a digest there)
  }
  const user = await getUser();
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col font-sans">
        <header className="border-b border-zinc-200 dark:border-zinc-800">
          <nav className="mx-auto flex max-w-5xl items-center gap-5 px-6 py-3">
            <span className="font-semibold">Proof of Purchase</span>
            {stub && <span className={`${chip} bg-amber-100 text-amber-800`}>STUB DATA</span>}
            <span className="flex-1" />
            {NAV.map(([label, href]) => (
              <Link key={href} href={href} className={link}>
                {label}
              </Link>
            ))}
            {user?.manager && (
              <Link href="/approvals" className={link}>
                Approvals
              </Link>
            )}
            {user ? (
              <form method="post" action="/act/logout" className="flex items-center gap-2 text-sm">
                <span>{user.name}</span>
                {user.manager && <span className={`${chip} bg-blue-100 text-blue-800`}>Manager</span>}
                <button className="text-zinc-500 underline">Sign out</button>
              </form>
            ) : (
              <Link href="/login" className={link}>
                Sign in
              </Link>
            )}
          </nav>
        </header>
        {down && (
          <p className="bg-red-100 px-6 py-2 text-center text-sm text-red-800">{`API unreachable at ${API_URL}`}</p>
        )}
        <main className="mx-auto w-full max-w-5xl p-6">{children}</main>
      </body>
    </html>
  );
}
