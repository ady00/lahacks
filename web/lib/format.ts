import type { FixStep } from "./types";

export const usd = (n: number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

/** Jev probability as a whole percent; empty for non-model facts (p is null). */
export function pct(p: number | null | undefined): string {
  return p == null ? "" : `${Math.round(p * 100)}%`;
}

/** One fix step as a sentence. An amount step reads as a ceiling, per the contract. */
export function fixLine(s: FixStep): string {
  if (s.fact === "amount") return `amount: keep it at or under ${usd(Number(s.to))}`;
  return `${s.fact}: ${s.from ?? "unknown"} → ${s.to}`;
}
