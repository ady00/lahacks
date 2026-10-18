// Re-exports of the API's OpenAPI schema. Regenerate lib/openapi.d.ts when Person A changes a shape:
//   pnpm dlx openapi-typescript http://localhost:8000/openapi.json -o lib/openapi.d.ts
import type { components } from "./openapi";

type S = components["schemas"];
export type Case = S["Case"];
export type CaseList = S["CaseList"];
export type Authorization = S["Authorization"];
export type LedgerOut = S["LedgerOut"];
export type LedgerRow = S["LedgerRow"];
export type AuditSummary = S["AuditSummary"];
export type PolicyOut = S["PolicyOut"];
export type PolicyAudit = S["PolicyAudit"];
export type EvalOut = S["EvalOut"];
export type Health = S["Health"];
export type FixStep = S["FixStep"];
export type Fact = S["Fact"];
export type Employee = S["Employee"];
export type EmployeeList = S["EmployeeList"];
export type ApplicableOut = S["ApplicableOut"];
export type ApplicableRule = S["ApplicableRule"];
export type BankRulesOut = S["BankRulesOut"];
export type BankRule = S["BankRule"];

// Not in the generated schema yet (POST /policy/rules/draft): a translated rule plus Z3's checks on it.
export type Rule = { id: string; layer: string; text: string; when?: unknown; require?: unknown; custom?: boolean };
export type RuleDraft = { rule: Rule; dead: boolean; conflicts: PolicyAudit["conflicts"] };
