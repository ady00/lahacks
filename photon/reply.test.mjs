import { test } from "node:test";
import assert from "node:assert/strict";
import { parseReply } from "./reply.mjs";

test("bare yes/no decide the only waiting case", () => {
  assert.deepEqual(parseReply("Yes", ["c_1"]), { approved: true, caseId: "c_1" });
  assert.deepEqual(parseReply("no thanks", ["c_1"]), { approved: false, caseId: "c_1" });
  assert.deepEqual(parseReply("👍", ["c_1"]), { approved: true, caseId: "c_1" });
});

test("a case id in the reply wins, whatever is waiting", () => {
  assert.deepEqual(parseReply("approve C_8F2A", []), { approved: true, caseId: "c_8f2a" });
  assert.deepEqual(parseReply("reject c_2", ["c_1", "c_2"]), { approved: false, caseId: "c_2" });
});

test("ambiguous or empty queue asks instead of guessing", () => {
  assert.ok("error" in parseReply("yes", ["c_1", "c_2"]));
  assert.ok("error" in parseReply("yes", []));
});

test("anything else is not an answer", () => {
  assert.equal(parseReply("how much was it?", ["c_1"]), null);
  assert.equal(parseReply("nothing", ["c_1"]), null); // "no" must be a whole word
  assert.equal(parseReply("yesterday", ["c_1"]), null);
});
