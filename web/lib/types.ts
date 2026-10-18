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
