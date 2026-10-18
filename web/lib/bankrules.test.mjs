// Run: node --test lib/bankrules.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { DEFAULT_RULES, parseBankRules } from "./bankrules.ts";

test("parseBankRules reads the default set cleanly", () => {
  const { rules, errors } = parseBankRules(DEFAULT_RULES);
  assert.deepEqual(errors, []);
  assert.equal(rules.length, 8);
  assert.deepEqual(rules[4], { id: "delta", contains: ["DELTA"], amount_min: 0, amount_max: 1000, category: "Travel" });
  assert.deepEqual(rules[0], { id: "uber", contains: ["UBER"], amount_min: null, amount_max: null, category: "Travel" });
});

test("parseBankRules reports bad lines by number and keeps the good ones", () => {
  const { rules, errors } = parseBankRules("ok | A | | | X\n\nbad | A | x | | X\nshort | A\n | A | | | X\nok | B | | | Y");
  assert.equal(rules.length, 1);
  assert.deepEqual(errors, [
    "Line 3: min and max must be numbers or blank",
    "Line 4: expected 5 fields separated by |, got 2",
    "Line 5: the id is blank",
    'Line 6: the id "ok" is used twice',
  ]);
});
