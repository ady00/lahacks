"use client"; // the only way a layout learns the current path; plain <a> stays so the refresh timer never pulls users back

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

export function NavLink({ href, children }: { href: string; children: ReactNode }) {
  const path = usePathname();
  const current = href === "/" ? path === "/" || path.startsWith("/cases") : path.startsWith(href);
  return (
    <a
      href={href}
      aria-current={current ? "page" : undefined}
      className="group relative flex h-11 items-center font-display text-[14px] transition-colors duration-200 md:h-16"
    >
      <span className={`transition-all duration-200 ${current ? "font-semibold text-secondary" : "text-[#64748B] group-hover:text-ink group-hover:-translate-y-0.5"}`}>
        {children}
      </span>
      {current ? (
        <span className="absolute bottom-[6px] left-1/2 h-0.5 w-5 -translate-x-1/2 rounded-full bg-secondary shadow-[0_1px_4px_rgba(145,73,196,0.4)] md:bottom-[15px]" />
      ) : (
        <span className="absolute bottom-[6px] left-1/2 h-0.5 w-0 -translate-x-1/2 rounded-full bg-zinc-300 transition-all duration-200 group-hover:w-3.5 md:bottom-[15px]" />
      )}
    </a>
  );
}
