"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { factValue, probabilityLabel, previewOverrides, visibleGraph, type CaseGraph, type FactNode } from "@/lib/graph";
import { fixLine } from "@/lib/format";
import styles from "./PurchaseGraph.module.css";

function DependencyGraph({ graph }: { graph: CaseGraph }) {
  const [showAll, setShowAll] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const { facts, rules, edges } = visibleGraph(graph, showAll);
  const rule = rules.find(r => r.id === selected);
  const fact = facts.find(f => f.id === selected);
  const dependencies = new Set(rule ? [...rule.condition_facts, ...rule.requirement_facts] : []);
  const evidence = new Set(rule?.evidence_facts ?? []);
  const height = Math.max(facts.length * 118, rules.length * 152, 140);
  const centers = new Map<string, { x: number; y: number }>([
    ...facts.map((f, i) => [f.id, { x: 270, y: i * 118 + 52 }] as const),
    ...rules.map((r, i) => [r.id, { x: 760, y: i * 152 + 69 }] as const),
    ["verdict", { x: 1000, y: height / 2 }],
  ]);
  const hidden = graph.nodes.filter(n => n.kind === "rule" && n.status === "inactive").length;
  return <>
    <div className={styles.toolbar}>
      <label><input type="checkbox" checked={showAll} onChange={e => { setShowAll(e.target.checked); setSelected(null); }} /> Show all rules{hidden > 0 && ` (${hidden} inactive)`}</label>
      <span>Red: violated · Amber: uncertain · Green: satisfied · Gray: inactive</span>
    </div>
    <div className={styles.stage} style={{ height }} aria-label="Purchase facts, policy rules, and verdict">
      <span className={styles.columnTitle} style={{ left: 0 }}>Purchase facts</span>
      <span className={styles.columnTitle} style={{ left: "39%" }}>Policy rules</span>
      <span className={styles.columnTitle} style={{ left: "83%" }}>Z3 result</span>
      <svg className={styles.wires} viewBox={`0 0 1000 ${height}`} preserveAspectRatio="none" aria-hidden="true">
        {edges.map(e => {
          const from = centers.get(e.source), to = centers.get(e.target);
          if (!from || !to) return null;
          const endX = e.target === "verdict" ? 830 : 390;
          const active = !selected || e.source === selected || e.target === selected;
          return <path key={e.id} d={`M ${from.x} ${from.y} C ${(from.x + endX) / 2} ${from.y}, ${(from.x + endX) / 2} ${to.y}, ${endX} ${to.y}`}
            fill="none" stroke={e.contradiction_evidence ? "#dc2626" : active && selected ? "#2563eb" : "#94a3b8"}
            strokeWidth={active && selected ? 2.5 : 1.5} strokeDasharray={e.contradiction_evidence ? undefined : "5 4"} opacity={active ? .85 : .16} />;
        })}
      </svg>
      {facts.map((f, i) => <button key={f.id} type="button" aria-pressed={selected === f.id} onClick={() => setSelected(selected === f.id ? null : f.id)}
        className={[styles.node, styles.fact, !f.known && styles.uncertain, selected === f.id && styles.selected,
          evidence.has(f.name) ? styles.evidence : dependencies.has(f.name) ? styles.dependency : rule ? styles.dim : ""].filter(Boolean).join(" ")}
        style={{ top: i * 118 }}>
        <span className={styles.label}>{f.label}{f.changed && " · changed"}</span>
        <span className={styles.value}>{factValue(f)}</span>
        <span className={styles.meta}>Source: {f.source}{evidence.has(f.name) ? " · contradiction evidence" : ""}</span>
        {probabilityLabel(f) && <span className={styles.meta}>{probabilityLabel(f)}</span>}
      </button>)}
      {rules.map((r, i) => <button key={r.id} type="button" aria-pressed={selected === r.id} onClick={() => setSelected(selected === r.id ? null : r.id)}
        className={[styles.node, styles.rule, styles[r.status], selected === r.id && styles.selected,
          fact && ![...r.condition_facts, ...r.requirement_facts].includes(fact.name) && styles.dim].filter(Boolean).join(" ")}
        style={{ top: i * 152 }}>
        <span className={styles.label}>{r.layer} · Rule {r.rule_id}</span>
        <span className={styles.badge}>{r.status}</span>
        <span className={styles.ruleText}>{r.label}</span>
        <span className={styles.ruleLogic}>When: {r.condition}</span>
        <span className={styles.ruleLogic}>Requires: {r.requirement}</span>
      </button>)}
      <div className={`${styles.node} ${styles.verdict} ${styles[graph.verdict]}`} style={{ top: height / 2 - 45 }}>
        <span className={styles.label}>{graph.preview ? "Hypothetical" : "Saved"} verdict</span>
        <span className={styles.badge}>{graph.verdict}</span>
        <span className={styles.meta}>Existing policy engine</span>
      </div>
    </div>
    {!rules.length && <p className={styles.subtitle}>No active rules. Use “Show all rules” to inspect inactive conditions.</p>}
    <div className={styles.details} aria-live="polite">
      {rule ? <>
        <strong>{rule.layer} · Rule {rule.rule_id}: {rule.status}</strong>
        <p>{rule.label}</p>
        <p><strong>Condition ({rule.condition_state}):</strong> {rule.condition}</p>
        <p><strong>Requirement ({rule.requirement_state}):</strong> {rule.requirement}</p>
        <p><strong>Z3 contradiction evidence:</strong> {rule.evidence_facts.join(", ") || "None reported"}</p>
        <p><strong>Other referenced facts:</strong> {[...dependencies].filter(n => !evidence.has(n)).join(", ") || "None"}</p>
      </> : fact ? <>
        <strong>{fact.label}: {factValue(fact)}</strong>
        <p>Source: {fact.source}{probabilityLabel(fact) && ` · ${probabilityLabel(fact)}`}</p>
        <p>Evidence reference: {fact.evidence_ref ?? "No saved evidence reference"}</p>
        <p>Referenced by: {rules.filter(r => [...r.condition_facts, ...r.requirement_facts].includes(fact.name)).map(r => `${r.layer} ${r.rule_id}`).join(", ") || "No visible rules"}</p>
      </> : <p>Select a rule to inspect its logic and dependencies. Solid red connections identify facts in Z3’s reported contradiction evidence; dashed connections show other dependencies. This is a policy dependency graph with Z3 results, not an internal solver reasoning trace.</p>}
    </div>
  </>;
}

export function PurchaseGraph({ initialGraph, awaitingApproval, children }: {
  initialGraph: CaseGraph | null; awaitingApproval: boolean; children: ReactNode;
}) {
  const router = useRouter();
  const [previewMode, setPreviewMode] = useState(false);
  const [preview, setPreview] = useState<CaseGraph | null>(null);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => {
    if (!awaitingApproval || previewMode) return;
    const timer = setInterval(() => router.refresh(), 5000);
    return () => clearInterval(timer);
  }, [awaitingApproval, previewMode, router]);

  function reset() {
    controller.current?.abort(); controller.current = null;
    setPreviewMode(false); setPreview(null); setEdits({}); setError(null); setBusy(false);
  }
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!initialGraph) return;
    controller.current?.abort();
    const request = new AbortController(); controller.current = request;
    setBusy(true); setError(null); setPreview(null);
    try {
      const response = await fetch(`/api/cases/${encodeURIComponent(initialGraph.case_id)}/graph/preview`, {
        method: "POST", headers: { "content-type": "application/json" }, signal: request.signal,
        body: JSON.stringify({ overrides: previewOverrides(initialGraph.editable_fields, edits), base_facts_hash: initialGraph.base_facts_hash }),
      });
      if (!response.ok) throw new Error(response.status === 409 ? "Saved facts or policy changed. Reset and refresh the case before previewing again." :
        response.status === 422 ? "Invalid preview facts. Check the selected values." : "Preview analysis unavailable. No changes were saved.");
      const result: CaseGraph = await response.json();
      if (controller.current === request) setPreview(result);
    } catch (err) {
      if (!request.signal.aborted) setError(err instanceof Error ? err.message : "Preview unavailable");
    } finally {
      if (controller.current === request) setBusy(false);
    }
  }
  const current = preview ?? initialGraph;
  const savedFacts = new Map(initialGraph?.nodes.filter((n): n is FactNode => n.kind === "fact").map(f => [f.name, f]));
  return <>
    <fieldset disabled={previewMode} className={`${styles.saved} min-w-0 space-y-6`} aria-label="Saved purchase and real actions">
      {previewMode && <p className="text-sm font-semibold">Buttons are paused while you explore a what-if below. Reset the preview to use them.</p>}
      {children}
    </fieldset>
    <section className={styles.panel} aria-label="Purchase explanation">
      <div className={styles.header}>
        <div><h2 className="font-serif text-[18px] font-bold tracking-[-0.02em] text-ink">{current?.verdict === "violation" ? "Violation Overview" : "Rule Overview"}</h2>
          {initialGraph && <p className={styles.hash}>Policy {initialGraph.policy_version} · Facts {initialGraph.base_facts_hash.slice(0, 10)}</p>}</div>
        {initialGraph && !previewMode && <button type="button" className={styles.button} onClick={() => setPreviewMode(true)}>What if?</button>}
      </div>
      {!initialGraph ? <p className={styles.subtitle}>The rule-by-rule graph is not available for this case. <button className={styles.button} onClick={() => router.refresh()}>Try again</button></p> : <>
        {previewMode && <>
          <div className={styles.banner} role="status">
            <strong>Hypothetical—no changes saved</strong>
            <p>Real purchase actions are disabled during preview. Approval here is an assumption; only the existing approval workflow records approval.</p>
            <div className={styles.compare}>
              <div className={styles[initialGraph.saved_verdict]}>Saved: <strong>{initialGraph.saved_verdict}</strong></div>
              <div className={preview ? styles[preview.verdict] : ""}>Hypothetical: <strong>{busy ? "Evaluating…" : error ? "Unavailable" : preview?.verdict ?? "Not evaluated"}</strong></div>
            </div>
          </div>
          <form onSubmit={submit}>
            <p className={styles.subtitle}>Override facts below. Pick “Unknown” to drop one.</p>
            <div className={styles.fields}>
              {initialGraph.editable_fields.map(field => {
                const enabled = Object.hasOwn(edits, field.name);
                const saved = savedFacts.get(field.name);
                return <div key={field.name} className={styles.field}>
                  <label><input type="checkbox" checked={enabled} disabled={busy} onChange={e => {
                    setPreview(null); setError(null);
                    setEdits(old => { const next = { ...old }; if (e.target.checked) next[field.name] = saved?.value == null ? "" : String(saved.value); else delete next[field.name]; return next; });
                  }} />{field.label} <span className={styles.meta}>Saved: {saved ? factValue(saved) : "Unknown"}</span></label>
                  {enabled && (field.kind === "bool" || field.kind === "enum" ? <select aria-label={`Hypothetical ${field.label}`} disabled={busy} value={edits[field.name]} onChange={e => { setEdits({ ...edits, [field.name]: e.target.value }); setPreview(null); setError(null); }}>
                    <option value="">Unknown</option>{(field.kind === "bool" ? ["true", "false"] : field.values ?? []).map(v => <option key={v} value={v}>{v}</option>)}
                  </select> : <input aria-label={`Hypothetical ${field.label}`} type="number" disabled={busy} value={edits[field.name]} placeholder="Unknown"
                    step={field.kind === "int" ? 1 : "any"} min={field.name === "amount" ? .01 : field.lo ?? undefined} max={field.hi ?? undefined}
                    onChange={e => { setEdits({ ...edits, [field.name]: e.target.value }); setPreview(null); setError(null); }} />)}
                </div>;
              })}
            </div>
            <div className={styles.toolbar}>
              <button disabled={busy} className={`${styles.button} ${styles.primary}`}>{busy ? "Evaluating…" : "Preview changes"}</button>
              <button type="button" className={styles.button} onClick={reset}>Reset preview</button>
            </div>
          </form>
          {error && <p role="alert" className={styles.error}>{error}</p>}
          {preview && <div className={styles.details}>
            <strong>Hypothetical next steps</strong>
            {preview.questions.map(q => <p key={q.fact}>Question: {q.text}</p>)}
            {preview.fix?.map((fix, i) => <p key={i}>Proposed fix: {fixLine(fix)}</p>)}
            {!preview.questions.length && !preview.fix?.length && <p>No follow-up questions or fixes returned.</p>}
          </div>}
        </>}
        {current && <DependencyGraph key={`${current.facts_hash}:${current.preview}`} graph={current} />}
      </>}
    </section>
  </>;
}
