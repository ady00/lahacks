// Run: node --test lib/format.test.mjs   (Node strips the types in format.ts itself; no build step)
import { test } from "node:test";
import assert from "node:assert/strict";
import { pct, fixLine, usd, when, valueText, headline, expr, requireText } from "./format.ts";

test("pct renders Jev probabilities and nothing for null", () => {
  assert.equal(pct(0.97), "97%");
  assert.equal(pct(0.08), "8%");
  assert.equal(pct(null), "");
  assert.equal(pct(undefined), "");
});

test("fixLine: boolean, enum, unknown-from, amount", () => {
  assert.equal(fixLine({ fact: "pre_approved", from: false, to: true }), "Manager pre-approved: No → Yes");
  assert.equal(fixLine({ fact: "coded_account", from: "travel", to: "meals_50" }), "Posts to account: travel (Travel) → meals_50 (Meals, 50% deductible)");
  assert.equal(fixLine({ fact: "receipt_attached", from: null, to: true }), "Receipt attached: unknown → Yes");
  assert.equal(fixLine({ fact: "amount", from: 48, to: 35 }), "Keep the amount at or under $35.00");
});

test("usd and when", () => {
  assert.equal(usd(48), "$48.00");
  assert.equal(usd(12.5), "$12.50");
  assert.equal(when("2026-10-17T19:30:00-07:00"), "Oct 17, 2026, 7:30 PM");
  assert.equal(when("garbage"), "garbage");
  assert.equal(when(null), "");
});

test("valueText and headline", () => {
  assert.equal(valueText("hour", 22), "22:00");
  assert.equal(valueText("client_present", true), "Yes");
  const base = { verdict: "violation", facts: { amount: { value: 48 } }, awaiting_approval: true, approval: null, authorization: null, fix: [] };
  assert.equal(headline(base).title, "Needs manager approval.");
  assert.equal(headline({ ...base, verdict: "compliant", awaiting_approval: false }).title, "You can buy this.");
  assert.equal(headline({ ...base, awaiting_approval: false, fix: null }).next, "No change you control makes this compliant.");
  assert.equal(headline({ ...base, awaiting_approval: false, approval: { approved: false } }).title, "Your manager rejected this.");
});

test("rule expressions read as sentences", () => {
  assert.equal(expr({ gt: ["amount", 35] }), "Amount > $35.00");
  assert.equal(expr({ and: [{ eq: ["role", "intern"] }, { in: ["expense_kind", ["rideshare", "airfare"]] }] }), "Role is intern and Expense type is one of rideshare, airfare");
  assert.equal(expr({ and: [{ eq: ["expense_kind", "meal"] }, { not: "at_company_event" }] }), "Expense type is meal and not At a company event");
  assert.equal(expr({ eq: ["client_present", true] }), "Client present");
  assert.equal(requireText("pre_approved"), "Requires Manager pre-approved");
  assert.equal(requireText(false), "Never allowed");
  assert.equal(requireText({ and: ["pre_approved", "receipt_attached"] }), "Requires Manager pre-approved and Receipt attached");
  assert.equal(requireText({ eq: ["coded_account", "meals_50"] }), "Requires Posts to account is meals_50 (Meals, 50% deductible)");
});
