import type { Case, FixStep } from "./types";

export const usd = (n: number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);

/** Jev probability as a whole percent; empty for non-model facts (p is null). */
export function pct(p: number | null | undefined): string {
  return p == null ? "" : `${Math.round(p * 100)}%`;
}

/** ISO timestamp as a short Los Angeles date and time (the product's clock); the raw string if it does not parse. */
export function when(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short", timeZone: "America/Los_Angeles" }).format(d);
}

// Internal fact names as a person reads them. Unknown names fall through unchanged.
const FACT_LABELS: Record<string, string> = {
  role: "Role",
  expense_kind: "Expense type",
  client_present: "Client or partner present",
  at_company_event: "At a team event",
  traveling: "On a business trip",
  government_present: "Government official present",
  round_trip: "Round trip",
  booked_via_navan: "Booked through Navan",
  approved_issue: "Approved issue attached",
  days_before_travel: "Days booked ahead",
  attendees: "People",
  nights: "Nights",
  days: "Days covered",
  travel_class: "Seat class",
  segment_hours: "Shortest segment (hours)",
  international: "International",
  customer_trip: "Customer, speaking or conference trip",
  frequent_traveler: "Frequent traveler",
  tall_traveler: "Over 6'5\"",
  car_above_intermediate: "Car above intermediate class",
  rental_car: "Rental car",
  mileage_and_fuel: "Mileage and fuel both claimed",
  tip_over_20: "Tip over 20%",
  cash_equivalent: "Cash or gift card",
  gift_occasion: "Gift occasion",
  includes_fees: "Includes setup or hardware fees",
  whole_family_plan: "Whole family plan",
  ap_approved: "AP Admin approved",
  on_leave: "On leave",
  personal_travel: "Personal travel",
  amount: "Amount",
  hour: "Hour of day",
  days_since_purchase: "Days since purchase",
  tenure_days: "Days since start date",
  pre_approved: "Manager pre-approved",
  receipt_attached: "Receipt attached",
  coded_account: "Posts to account",
  deductible: "Deductible",
  miles: "Miles",
  companion_present: "Spouse or family along",
  commuting: "Commuting",
};
export const factLabel = (name: string) => FACT_LABELS[name] ?? name;

// coded_account values: the suffix is the IRS deductibility the IRS rules encode.
const ACCOUNTS: Record<string, string> = {
  meals_50: "Meals, 50% deductible",
  meals_100: "Meals at a company event, 100% deductible",
  entertainment_0: "Entertainment, not deductible",
  travel: "Travel",
  office: "Office expenses",
  other: "Other",
};
export const accountLabel = (v: string) => ACCOUNTS[v] ?? v;

const SOURCES: Record<string, string> = {
  jev: "read from the description",
  text: "dollar figure in the description",
  employee: "employee record",
  approvals: "approval records",
  ledger: "ledger",
  derived: "from the date and time",
  rules: "set by the rules",
  answer: "answered here",
  user: "answered here",
  product: "product page",
  claude: "inferred from the description",
};
export const sourceLabel = (s: string) => SOURCES[s] ?? s;

/** A fact value as a person reads it: Yes/No, money, clock hour, account names. */
export function valueText(name: string, v: unknown): string {
  if (v === true) return "Yes";
  if (v === false) return "No";
  if (v == null) return "unknown";
  if (name === "amount") return usd(Number(v));
  if (name === "hour") return `${v}:00`;
  if (name === "coded_account") return accountLabel(String(v));
  return String(v);
}

/** One fix step as a sentence. An amount step reads as a ceiling, per the contract. */
export function fixLine(s: FixStep): string {
  if (s.fact === "amount") return `Keep the amount at or under ${usd(Number(s.to))}`;
  return `${factLabel(s.fact)}: ${valueText(s.fact, s.from)} → ${valueText(s.fact, s.to)}`;
}

/** The one sentence a person needs first, and what they can do next. */
export function headline(c: Case): { title: string; next: string } {
  if (c.authorization)
    return {
      title: "Approved. Your card is authorized.",
      next: `Spend up to ${usd(c.authorization.amount_limit)} at ${c.authorization.merchant_category}; the authorization expires ${when(c.authorization.expires_at)}.`,
    };
  if (c.verdict === "compliant")
    return {
      title: "You can buy this.",
      next: c.facts.amount ? "Authorize the card below to lock in the amount." : "Give the amount to get a card authorization.",
    };
  if (c.verdict === "undetermined")
    return { title: "One more detail decides it.", next: "Answer the question below; the rules re-check instantly." };
  if (c.awaiting_approval)
    return { title: "Needs manager approval.", next: "A manager decides on the Approvals page. This page updates on its own." };
  if (c.approval && !c.approval.approved)
    return { title: "Your manager rejected this.", next: "Change the purchase and check it again." };
  if (c.fix === null)
    return { title: "Not allowed as described.", next: "No change you control makes this compliant." };
  return { title: "Not allowed as described.", next: "Fix what is listed below, then check again." };
}

// Rule conditions (api policy `when` / `require`) as one readable line.
const OPS: Record<string, string> = { gt: ">", ge: "≥", lt: "<", le: "≤", eq: "is", ne: "is not" };
export function expr(e: unknown): string {
  if (typeof e === "string") return factLabel(e);
  if (typeof e === "boolean") return e ? "always" : "never";
  if (!e || typeof e !== "object") return String(e);
  const [op, arg] = Object.entries(e as Record<string, unknown>)[0] ?? ["?", null];
  if (op === "and" || op === "or") return (arg as unknown[]).map(expr).join(` ${op} `);
  if (op === "not") return `not ${expr(arg)}`;
  if (op === "in") {
    const [f, vs] = arg as [string, unknown[]];
    return `${factLabel(f)} is one of ${vs.map((v) => valueText(f, v)).join(", ")}`;
  }
  if (op in OPS) {
    const [f, v] = arg as [string | { per: [string, string] }, unknown];
    if (typeof f === "object") return `${factLabel(f.per[0])} per ${factLabel(f.per[1]).toLowerCase()} ${OPS[op]} ${valueText(f.per[0], v)}`;
    if (op === "eq" && typeof v === "boolean") return v ? factLabel(f) : `not ${factLabel(f)}`;
    return `${factLabel(f)} ${OPS[op]} ${valueText(f, v)}`;
  }
  return JSON.stringify(e);
}
export function requireText(r: unknown): string {
  if (r === false) return "Never allowed";
  if (r === true) return "Always allowed";
  return `Requires ${expr(r)}`;
}
