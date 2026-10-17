import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import { API_URL, get } from "@/lib/api";
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
  ["Approvals", "/approvals"],
] as const;

export default async function RootLayout({ children }: LayoutProps<"/">) {
  let stub = false;
  let down = false;
  try {
    stub = (await get<Health>("/health")).stub;
  } catch {
    down = true; // server-rendered, so the message survives production (error.tsx only gets a digest there)
  }
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col font-sans">
        <header className="border-b border-zinc-200 dark:border-zinc-800">
          <nav className="mx-auto flex max-w-5xl items-center gap-6 px-6 py-3">
            <span className="font-semibold">Proof of Purchase</span>
            {stub && (
              <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">STUB DATA</span>
            )}
            <span className="flex-1" />
            {NAV.map(([label, href]) => (
              <Link key={href} href={href} className="text-sm text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100">
                {label}
              </Link>
            ))}
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
