import type { Case, FixStep } from "./types";

// Additive /cases/{id}/graph contract. Values and evaluations come from the API.
export type Value = string | number | boolean | null;
export type FactNode = {
  id: string; kind: "fact"; name: string; label: string; value: Value;
  known: boolean; source: string; p: number | null;
  probability_kind: "p_true" | "value_confidence" | null;
  evidence_ref: string | null; changed: boolean;
};
export type RuleNode = {
  id: string; kind: "rule"; rule_id: string; label: string; layer: string;
  status: "inactive" | "violated" | "uncertain" | "satisfied";
  condition: string; requirement: string;
  condition_state: "true" | "false" | "unknown";
  requirement_state: "true" | "false" | "unknown";
  condition_facts: string[]; requirement_facts: string[]; evidence_facts: string[];
};
export type VerdictNode = { id: string; kind: "verdict"; label: string; status: Case["verdict"] };
export type GraphEdge = {
  id: string; source: string; target: string;
  relation: "condition" | "requirement" | "both" | "outcome";
  contradiction_evidence: boolean;
};
export type PreviewField = { name: string; label: string; kind: string; values: string[] | null; lo: number | null; hi: number | null };
export type CaseGraph = {
  case_id: string; policy_version: string; facts_hash: string; base_facts_hash: string;
  preview: boolean; saved_verdict: Case["verdict"]; verdict: Case["verdict"];
  nodes: (FactNode | RuleNode | VerdictNode)[]; edges: GraphEdge[];
  editable_fields: PreviewField[]; questions: Case["questions"]; fix: FixStep[] | null;
};

export function factValue(fact: FactNode): string {
  if (!fact.known) return "Unknown";
  if (fact.name === "amount" && typeof fact.value === "number")
    return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(fact.value);
  return String(fact.value);
}

export function probabilityLabel(fact: FactNode): string | null {
  if (fact.p == null || !fact.probability_kind) return null;
  return `${fact.probability_kind === "p_true" ? "P(true)" : "Value confidence"}: ${Number((fact.p * 100).toFixed(2))}%`;
}

export function visibleGraph(graph: CaseGraph, showAll: boolean) {
  const rules = graph.nodes.filter((n): n is RuleNode => n.kind === "rule" && (showAll || n.status !== "inactive"));
  const used = new Set(rules.flatMap(r => [...r.condition_facts, ...r.requirement_facts]));
  const facts = graph.nodes.filter((n): n is FactNode => n.kind === "fact" && (showAll || used.has(n.name)));
  const ids = new Set([...facts, ...rules].map(n => n.id).concat("verdict"));
  return { rules, facts, edges: graph.edges.filter(e => ids.has(e.source) && ids.has(e.target)) };
}

// Only serialize user-selected edits; empty string explicitly clears a fact.
export function previewOverrides(fields: PreviewField[], edits: Record<string, string>): Record<string, Value> {
  const result: Record<string, Value> = {};
  for (const field of fields) {
    if (!Object.hasOwn(edits, field.name)) continue;
    const value = edits[field.name];
    if (value === "") result[field.name] = null;
    else if (field.kind === "bool") {
      if (value !== "true" && value !== "false") throw new Error(`Invalid ${field.label}`);
      result[field.name] = value === "true";
    } else if (field.kind === "int" || field.kind === "real") {
      const number = Number(value);
      if (!Number.isFinite(number) || (field.kind === "int" && !Number.isInteger(number))) throw new Error(`Invalid ${field.label}`);
      result[field.name] = number;
    } else result[field.name] = value;
  }
  return result;
}
