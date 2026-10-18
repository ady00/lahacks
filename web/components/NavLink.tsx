"use client"; // the only way a layout learns the current path; plain <a> stays so the refresh timer never pulls users back

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

export function NavLink({ href, children }: { href: string; children: ReactNode }) {
  const path = usePathname();
  const current = href === "/" ? path === "/" || path.startsWith("/cases") : path.startsWith(href);
  return (
    <a href={href} aria-current={current ? "page" : undefined} className="relative flex h-11 items-center font-display text-[14px] md:h-16">
      <span className={current ? "text-secondary" : "text-[#64748B] hover:text-ink"}>{children}</span>
      {current && <span className="absolute bottom-[6px] left-1/2 md:bottom-[15px] h-0.5 w-5 -translate-x-1/2 rounded-sm bg-secondary" />}
    </a>
  );
}
