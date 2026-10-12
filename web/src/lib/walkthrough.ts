/**
 * The approval flow as a graph, and the path a payment takes through it.
 * Every branch is a rule the code applies; Gemini only reads, writes and looks things up.
 * `built: false` marks steps that are designed but not in the app yet.
 */

export type Role = "data" | "ai" | "code" | "human";
export type Tone = "ok" | "stop" | "hold";

export type FlowNode =
  | { id: string; kind: "step"; role: Role; title: string; detail: string; built: boolean; x: number; y: number }
  | { id: string; kind: "decision"; title: string; detail?: string; built: boolean; x: number; y: number }
  | { id: string; kind: "end"; tone: Tone; title: string; detail: string; built: boolean; x: number; y: number };

export type FlowEdge = {
  id: string;
  source: string;
  target: string;
  when?: boolean; // the answer that takes this branch out of a decision
  loop?: boolean; // drawn for context, never walked
  sourceHandle?: "top" | "bottom" | "left" | "right";
  targetHandle?: "top" | "bottom" | "left" | "right";
};

export type Scenario = {
  id: string;
  title: string;
  summary: string;
  normal: boolean;
  answers: Record<string, boolean>;
  outcome: string;
};

const SPINE = 300;
const DECISION = 320; // decisions are 240 wide, steps 280, ends 240
const RIGHT = 700;
const LEFT = -60;
const END = SPINE + 20;

export const NODES: FlowNode[] = [
  { id: "start", kind: "step", role: "data", title: "Payment waits for approval", detail: "Entered in corporate internet banking", built: true, x: SPINE, y: 0 },
  { id: "read", kind: "step", role: "ai", title: "Reader (Gemini)", detail: "Reads the instruction: email, chat, invoice", built: true, x: SPINE, y: 100 },
  { id: "check", kind: "step", role: "code", title: "Rules (code)", detail: "Compare the payment and the instruction with the ledger", built: true, x: SPINE, y: 200 },
  { id: "external", kind: "decision", title: "Flagged by an external list?", detail: "Web Risk, company registry", built: false, x: DECISION, y: 310 },
  { id: "differs", kind: "decision", title: "Differs from the ledger?", built: true, x: DECISION, y: 450 },
  { id: "explain", kind: "step", role: "ai", title: "Explainer (Gemini)", detail: "What differs and what to do; code checks the wording", built: true, x: SPINE, y: 590 },
  { id: "has-phone", kind: "decision", title: "Ledger has a number to call?", detail: "A new payee has none", built: true, x: DECISION, y: 690 },
  { id: "finder", kind: "step", role: "ai", title: "Finder (Gemini + Google Search)", detail: "Looks up the payee's official number", built: false, x: RIGHT, y: 705 },
  { id: "found", kind: "decision", title: "Official number found?", built: false, x: RIGHT + 20, y: 820 },
  { id: "call", kind: "step", role: "human", title: "Approver calls", detail: "The ledger or official number, never the one in the message", built: true, x: SPINE, y: 840 },
  { id: "confirmed", kind: "decision", title: "Did they confirm the request?", built: true, x: DECISION, y: 950 },
  { id: "second", kind: "step", role: "human", title: "Call logged, second approval", detail: "Who called, when, which number", built: false, x: SPINE, y: 1090 },
  { id: "send", kind: "step", role: "data", title: "Transfer sent", detail: "", built: true, x: SPINE, y: 1190 },
  { id: "recorded", kind: "end", tone: "ok", title: "Account verified in the ledger", detail: "Next time it goes through quietly", built: false, x: END, y: 1290 },
  { id: "quiet", kind: "end", tone: "ok", title: "Approve as usual", detail: "Nothing to show", built: true, x: LEFT, y: 470 },
  { id: "blocked-list", kind: "end", tone: "stop", title: "Cannot be approved", detail: "An external list flagged it", built: false, x: RIGHT + 20, y: 330 },
  { id: "blocked-no-number", kind: "end", tone: "stop", title: "Cannot be approved", detail: "No independent number to check with", built: false, x: RIGHT + 20, y: 960 },
  { id: "held", kind: "end", tone: "hold", title: "Held, not sent", detail: "Likely impersonation; tell the bank", built: true, x: LEFT, y: 970 },
];

export const EDGES: FlowEdge[] = [
  { id: "start-read", source: "start", target: "read" },
  { id: "read-check", source: "read", target: "check" },
  { id: "check-external", source: "check", target: "external" },
  { id: "external-yes", source: "external", target: "blocked-list", when: true, sourceHandle: "right", targetHandle: "left" },
  { id: "external-no", source: "external", target: "differs", when: false },
  { id: "differs-no", source: "differs", target: "quiet", when: false, sourceHandle: "left", targetHandle: "right" },
  { id: "differs-yes", source: "differs", target: "explain", when: true },
  { id: "explain-phone", source: "explain", target: "has-phone" },
  { id: "phone-yes", source: "has-phone", target: "call", when: true },
  { id: "phone-no", source: "has-phone", target: "finder", when: false, sourceHandle: "right", targetHandle: "left" },
  { id: "finder-found", source: "finder", target: "found" },
  { id: "found-yes", source: "found", target: "call", when: true, sourceHandle: "left", targetHandle: "right" },
  { id: "found-no", source: "found", target: "blocked-no-number", when: false },
  { id: "call-confirmed", source: "call", target: "confirmed" },
  { id: "confirmed-no", source: "confirmed", target: "held", when: false, sourceHandle: "left", targetHandle: "right" },
  { id: "confirmed-yes", source: "confirmed", target: "second", when: true },
  { id: "second-send", source: "second", target: "send" },
  { id: "send-recorded", source: "send", target: "recorded" },
  { id: "recorded-check", source: "recorded", target: "check", loop: true, sourceHandle: "left", targetHandle: "left" },
];

export const SCENARIOS: Scenario[] = [
  {
    id: "routine",
    title: "Routine invoice",
    summary: "A regular supplier, its registered account, a usual amount.",
    normal: true,
    answers: { external: false, differs: false },
    outcome: "Nothing differs, so nothing is shown. The approver approves as usual.",
  },
  {
    id: "genuine-account-change",
    title: "Genuine account change",
    summary: "A supplier really moved banks after a merger.",
    normal: true,
    answers: { external: false, differs: true, "has-phone": true, confirmed: true },
    outcome: "The supplier confirms on the ledger number. Sent, and the new account is now verified.",
  },
  {
    id: "new-supplier",
    title: "First payment to a new supplier",
    summary: "A real company with no history in the ledger yet.",
    normal: true,
    answers: { external: false, differs: true, "has-phone": false, found: true, confirmed: true },
    outcome: "Gemini finds the official number, the supplier confirms, and the account is recorded.",
  },
  {
    id: "lookalike-account-change",
    title: "Account change from a look-alike domain",
    summary: "yarnada-kenzai.example asks to pay a new account.",
    normal: false,
    answers: { external: false, differs: true, "has-phone": true, confirmed: false },
    outcome: "The real supplier, called on the ledger number, never sent it. Held.",
  },
  {
    id: "ceo-line-new-payee",
    title: "The CEO on LINE, a new payee",
    summary: "'In a meeting, pay ¥3,000,000 today.'",
    normal: false,
    answers: { external: false, differs: true, "has-phone": true, confirmed: false },
    outcome: "The CEO, called on the number in the ledger, knows nothing about it. Held.",
  },
  {
    id: "fake-supplier",
    title: "Invoice from a supplier that does not exist",
    summary: "A convincing invoice; the company cannot be found anywhere official.",
    normal: false,
    answers: { external: false, differs: true, "has-phone": false, found: false },
    outcome: "There is no independent number to check with, so it cannot be approved.",
  },
  {
    id: "phishing-link",
    title: "A phishing link in the instruction",
    summary: "The email links to a page Google lists as phishing.",
    normal: false,
    answers: { external: true },
    outcome: "Web Risk lists the link, so it cannot be approved.",
  },
];

const nodeById = new Map(NODES.map((n) => [n.id, n]));

export function walk(s: Scenario): { nodes: string[]; edges: string[]; end: string } {
  const nodes = ["start"];
  const edges: string[] = [];
  for (let at = nodeById.get("start")!; at.kind !== "end"; ) {
    const out = EDGES.filter((e) => e.source === at.id && !e.loop);
    let next: FlowEdge | undefined;
    if (at.kind === "decision") {
      if (!(at.id in s.answers)) throw new Error(`${s.id}: no answer for "${at.id}"`);
      next = out.find((e) => e.when === s.answers[at.id]);
    } else {
      next = out[0];
    }
    if (!next) throw new Error(`${s.id}: dead end at "${at.id}"`);
    edges.push(next.id);
    nodes.push(next.target);
    at = nodeById.get(next.target)!;
  }
  return { nodes, edges, end: nodes[nodes.length - 1] };
}
