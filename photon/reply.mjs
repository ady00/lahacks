// A manager's text reply → the /approve call it means. Pure, so it is testable without Photon or the API.
const YES = /^(?:(?:yes|y|yep|yeah|approved?|ok(?:ay)?)\b|👍)/i;
const NO = /^(?:(?:no|n|nope|reject(?:ed)?|den(?:y|ied))\b|👎)/i;

/** @returns {{approved:boolean, caseId:string} | {error:string} | null} null = not an answer at all */
export function parseReply(text, waiting) {
  const t = text.trim();
  const approved = YES.test(t) ? true : NO.test(t) ? false : null;
  if (approved === null) return null;
  const id = t.match(/c_[0-9a-f]+/i)?.[0].toLowerCase();
  if (id) return { approved, caseId: id };
  if (waiting.length === 1) return { approved, caseId: waiting[0] };
  if (waiting.length === 0) return { error: "Nothing is waiting for approval right now." };
  return { error: `${waiting.length} cases are waiting; reply YES or NO with the case id, e.g. "yes ${waiting[0]}".` };
}
