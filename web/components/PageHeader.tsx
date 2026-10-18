import type { ReactNode } from "react";
import { h1, muted } from "@/lib/ui";

/** Title, one line of context, and the page's actions on the right: the header every page shares. */
export function PageHeader({ title, text, children }: { title: string; text?: string; children?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4 pb-6 pt-2">
      <div className="space-y-1.5">
        <h1 className={h1}>{title}</h1>
        {text && <p className={`max-w-[70ch] text-sm ${muted}`}>{text}</p>}
      </div>
      {children && <div className="flex items-center gap-3">{children}</div>}
    </div>
  );
}
