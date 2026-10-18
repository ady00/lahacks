import assert from "node:assert/strict";
import { test } from "node:test";
import { factValue, probabilityLabel, previewOverrides, visibleGraph } from "./graph.ts";

test("unknown and false remain distinct; probability means P(true), not confidence in false", () => {
  assert.equal(factValue({ known: false, value: false }), "Unknown");
  assert.equal(factValue({ known: true, value: false }), "false");
  assert.equal(factValue({ known: true, value: 48, name: "amount" }), "$48.00");
  assert.equal(probabilityLabel({ p: .08, probability_kind: "p_true" }), "P(true): 8%");
  assert.equal(probabilityLabel({ p: .97, probability_kind: "value_confidence" }), "Value confidence: 97%");
});

test("inactive rules and their exclusive dependencies collapse without dropping evidence edges", () => {
  const nodes = [
    { id: "a", kind: "fact", name: "amount" }, { id: "r", kind: "fact", name: "role" },
    { id: "active", kind: "rule", status: "violated", condition_facts: ["amount"], requirement_facts: [] },
    { id: "inactive", kind: "rule", status: "inactive", condition_facts: ["role"], requirement_facts: [] },
  ];
  const edges = [{ source: "a", target: "active", contradiction_evidence: true }, { source: "r", target: "inactive" }, { source: "active", target: "verdict" }];
  const shown = visibleGraph({ nodes, edges }, false);
  assert.deepEqual(shown.facts.map(f => f.id), ["a"]);
  assert.deepEqual(shown.rules.map(r => r.id), ["active"]);
  assert.equal(shown.edges[0].contradiction_evidence, true);
  assert.equal(visibleGraph({ nodes, edges }, true).rules.length, 2);
});

test("overrides retain false, parse numbers, clear unknown, and omit unselected fields", () => {
  const fields = [{ name: "pre_approved", kind: "bool" }, { name: "amount", kind: "real" }, { name: "role", kind: "enum" }, { name: "receipt_attached", kind: "bool" }];
  assert.deepEqual(previewOverrides(fields, { pre_approved: "false", amount: "48", role: "" }), { pre_approved: false, amount: 48, role: null });
  assert.throws(() => previewOverrides(fields, { amount: "NaN" }));
  assert.throws(() => previewOverrides(fields, { pre_approved: "yes" }));
});
