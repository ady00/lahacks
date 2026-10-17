// Run: node --test lib/format.test.mjs   (Node strips the types in format.ts itself; no build step)
import { test } from "node:test";
import assert from "node:assert/strict";
import { pct, fixLine, usd } from "./format.ts";

test("pct renders Jev probabilities and nothing for null", () => {
  assert.equal(pct(0.97), "97%");
  assert.equal(pct(0.08), "8%");
  assert.equal(pct(null), "");
  assert.equal(pct(undefined), "");
});

test("fixLine: boolean, enum, unknown-from, amount", () => {
  assert.equal(fixLine({ fact: "pre_approved", from: false, to: true }), "pre_approved: false → true");
  assert.equal(fixLine({ fact: "coded_account", from: "travel", to: "meals_50" }), "coded_account: travel → meals_50");
  assert.equal(fixLine({ fact: "receipt_attached", from: null, to: true }), "receipt_attached: unknown → true");
  assert.equal(fixLine({ fact: "amount", from: 48, to: 35 }), "amount: keep it at or under $35.00");
});

test("usd", () => {
  assert.equal(usd(48), "$48.00");
  assert.equal(usd(12.5), "$12.50");
});
