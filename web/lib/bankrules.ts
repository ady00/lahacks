import type { BankRule } from "./types";

// One rule per line, QuickBooks-style: id | words the description contains | min | max | category.
// Pure, so `node --test` covers it; the page only renders what this returns.
export const DEFAULT_RULES = `uber | UBER | | | Travel
uber-eats | UBER EATS | | | Meals
amazon | AMAZON | | | Office
aws | AMAZON WEB SERVICES | | | Software
delta | DELTA | 0 | 1000 | Travel
marriott | MARRIOTT | | | Travel
coffee | STARBUCKS | 0 | 15 | Office supplies
starbucks | STARBUCKS | | | Meals`;

const num = (s: string): number | null | undefined => (s === "" ? null : isNaN(Number(s)) ? undefined : Number(s));

export function parseBankRules(text: string): { rules: BankRule[]; errors: string[] } {
  const rules: BankRule[] = [];
  const errors: string[] = [];
  text.split("\n").forEach((line, i) => {
    if (!line.trim()) return;
    const parts = line.split("|").map((p) => p.trim());
    if (parts.length !== 5) return void errors.push(`Line ${i + 1}: expected 5 fields separated by |, got ${parts.length}`);
    const [id, words, min, max, category] = parts;
    const amount_min = num(min);
    const amount_max = num(max);
    if (!id) return void errors.push(`Line ${i + 1}: the id is blank`);
    if (!category) return void errors.push(`Line ${i + 1}: the category is blank`);
    if (amount_min === undefined || amount_max === undefined) return void errors.push(`Line ${i + 1}: min and max must be numbers or blank`);
    if (rules.some((r) => r.id === id)) return void errors.push(`Line ${i + 1}: the id "${id}" is used twice`);
    rules.push({ id, contains: words.split(/\s+/).filter(Boolean), amount_min, amount_max, category });
  });
  return { rules, errors };
}
