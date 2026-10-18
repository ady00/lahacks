import type { Metadata } from "next";
import { Inter, Literata, Young_Serif } from "next/font/google";
import { API_URL, get } from "@/lib/api";
import { getUser } from "@/lib/session";
import type { Health } from "@/lib/types";
import { NavLink } from "@/components/NavLink";
import "./globals.css";

const youngSerif = Young_Serif({ weight: "400", subsets: ["latin"], variable: "--font-young-serif" });
const literata = Literata({ subsets: ["latin"], variable: "--font-literata" });
const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "apriori · Proof of Purchase",
  description: "Purchase checks proven by Z3",
};

const NAV = [
  ["Check", "/"],
  ["Ledger", "/ledger"],
  ["Rules", "/rules"],
  ["Bank rules", "/bank-rules"],
  ["Evaluation", "/eval"],
] as const;

const initials = (name: string) =>
  name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]?.toUpperCase()).join("") || "?";

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
    <html lang="en" className={`${youngSerif.variable} ${literata.variable} ${inter.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col font-sans text-[14px]">
        <header className="bg-white shadow-[0_2px_3px_#00000033]">
          <nav className="mx-auto flex h-16 max-w-[1440px] items-center gap-4 px-6 sm:gap-8 sm:px-12">
            {/* eslint-disable-next-line @next/next/no-html-link-for-pages -- plain anchors on purpose, see c0dc517 */}
            <a href="/" className="font-display text-[29px] tracking-[-0.02em] text-ink [text-shadow:0_2px_3px_#00000033]">
              apriori
            </a>
            {stub && (
              <span className="hidden rounded bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800 sm:inline" title="The API is answering with sample data, not the real engine">
                Sample data
              </span>
            )}
            <div className="hidden flex-1 items-center justify-center gap-6 md:flex">
              {NAV.map(([label, href]) => (
                <NavLink key={href} href={href}>{label}</NavLink>
              ))}
              {user && <NavLink href="/you">For you</NavLink>}
            {user?.manager && <NavLink href="/approvals">Approvals</NavLink>}
            </div>
            <span className="flex-1 md:hidden" />
            {user ? (
              <div className="flex items-center gap-3">
                <div className="hidden text-right sm:block">
                  <div className="font-display text-[13px] text-ink">{user.name}</div>
                  <form method="post" action="/act/logout" className="text-[11px] font-medium text-[#94A3B8]">
                    {user.manager ? "Manager" : "Employee"} · <button className="hover:text-ink">Sign out</button>
                  </form>
                </div>
                <span className="flex size-8 items-center justify-center rounded-full bg-[#E2E8F0] text-[12px] font-semibold text-[#475569]">
                  {initials(user.name)}
                </span>
              </div>
            ) : (
              <NavLink href="/login">Sign in</NavLink>
            )}
          </nav>
          <div className="flex flex-wrap gap-x-5 px-6 md:hidden">
            {NAV.map(([label, href]) => (
              <NavLink key={href} href={href}>{label}</NavLink>
            ))}
            {user?.manager && <NavLink href="/approvals">Approvals</NavLink>}
          </div>
        </header>
        {down && (
          <p className="bg-red-100 px-6 py-2 text-center text-sm text-red-800">
            {`The API at ${API_URL} is not answering. Start it, then reload this page.`}
          </p>
        )}
        <main className="mx-auto w-full max-w-[1440px] px-6 pb-16 pt-6 sm:px-12">{children}</main>
      </body>
    </html>
  );
}
