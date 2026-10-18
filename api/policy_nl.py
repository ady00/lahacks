"""Natural language -> one policy rule, by shelling out to the local Claude Code CLI (`claude -p`).

ponytail: one translator, one function. Swap the body of `translate` for any other model when the API
leaves the laptop; the prompt and the JSON shape are the contract.
"""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import engine
from engine.schema import FACTS


class TranslateError(Exception):
    pass


def _claude() -> str | None:
    return shutil.which("claude") or next((p for p in [os.path.expanduser("~/.local/bin/claude")] if os.access(p, os.X_OK)), None)


def _prompt(text: str) -> str:
    facts = "\n".join(
        f"- {n}: {s.kind}" + (f", one of {list(s.values)}" if s.values else "") + (f", {s.lo}..{s.hi if s.hi is not None else ''}" if s.lo is not None else "")
        for n, s in FACTS.items())
    examples = json.loads((Path(engine.__file__).parent / "demo_policy.json").read_text())[:4]
    return f"""Translate one expense-policy sentence into a rule for a Z3 checker. Answer with ONE JSON object and nothing else.

Rule shape: {{"text": <the policy as one clean sentence>, "when": <condition>, "require": <obligation>}}
A rule means: whenever `when` holds, `require` must hold.

Expressions: a bare fact name (bool facts only), true/false, or one of
  {{"and": [e, e, ...]}}  {{"or": [e, e, ...]}}  {{"not": e}}
  {{"eq": [fact, value]}}  {{"neq": [fact, value]}}  {{"gt": [fact, n]}}  {{"ge": [fact, n]}}  {{"lt": [fact, n]}}  {{"le": [fact, n]}}
  {{"in": [fact, [value, ...]]}}
Facts (use only these names and values):
{facts}
Notes: "manager approval / pre-approval / sign-off" is pre_approved. "receipt" is receipt_attached. Times of day are `hour` (0-23).
Deductibility or posting rules set coded_account. A prohibition is "require": false. Amounts are USD numbers.

Examples:
{json.dumps(examples, indent=1)}

Policy sentence: {text.strip()}"""


def translate(text: str, timeout: float = 90) -> dict:
    """{"text", "when", "require"} for one sentence, or TranslateError with a message a person can read."""
    exe = _claude()
    if not exe:
        raise TranslateError("The Claude Code CLI is not installed on the API host, so sentences cannot be translated.")
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE")}  # a nested CLI refuses to start inside a session
    try:
        out = subprocess.run([exe, "-p", _prompt(text), "--output-format", "text"], capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        raise TranslateError("The translator took too long. Try a shorter sentence.")
    if out.returncode != 0:
        raise TranslateError(f"The translator failed: {(out.stderr or out.stdout).strip()[:300]}")
    m = re.search(r"\{.*\}", out.stdout, re.S)
    try:
        rule = json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        rule = None
    if not isinstance(rule, dict) or not {"text", "when", "require"} <= set(rule):
        raise TranslateError("The translator did not return a rule. Try rephrasing the sentence.")
    return {"text": str(rule["text"]), "when": rule["when"], "require": rule["require"]}
