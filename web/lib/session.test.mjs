// Run: node --test lib/session.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import { parseUser } from "./session.ts";

test("parseUser accepts the exact shape", () => {
  assert.deepEqual(parseUser('{"employee_id":"e_1","name":"Priya","manager":true}'), {
    employee_id: "e_1",
    name: "Priya",
    manager: true,
  });
});

test("parseUser rejects garbage, missing fields and wrong types", () => {
  assert.equal(parseUser(undefined), null);
  assert.equal(parseUser("not json"), null);
  assert.equal(parseUser('{"employee_id":"e_1"}'), null);
  assert.equal(parseUser('{"employee_id":"e_1","name":"P","manager":"yes"}'), null);
});
