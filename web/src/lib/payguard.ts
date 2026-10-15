// Types mirror agent/app/payguard (api.py, pipeline.py, models.py, reader.py, explain.py).

export type Channel = "email" | "line" | "sms" | "phone" | "in_person" | "edi" | "other";
export type Status = "pending" | "approved" | "held";
export type Tier = "pass" | "verify" | "block";
export type FindingCode =
  | "NEW_PAYEE"
  | "ACCOUNT_NOT_REGISTERED"
  | "ACCOUNT_RECENTLY_REGISTERED"
  | "HOLDER_MISMATCH"
  | "AMOUNT_ABOVE_HISTORY"
  | "SENDER_DOMAIN_LOOKALIKE"
  | "SENDER_DOMAIN_UNREGISTERED"
  | "UNUSUAL_CHANNEL"
  | "INSTRUCTION_MISMATCH"
  | "ACCOUNT_UNVERIFIED"
  | "URL_LISTED"
  | "COMPANY_NOT_FOUND"
  | "NEW_COMPANY"
  | "HOLDER_NOT_COMPANY"
  | "NEW_DOMAIN"
  | "NOT_IN_ORIGINAL"
  | "LOOKUP_FAILED";
export type InstructionField =
  | "sender_name"
  | "sender_address"
  | "payee_name"
  | "account_number"
  | "account_holder"
  | "amount";

export type BankAccount = {
  bank_name: string;
  branch_name: string;
  account_type: "ordinary" | "current";
  number: string;
  holder_kana: string;
};

export type Payment = {
  id: string;
  vendor_id: string | null;
  payee_name: string;
  account: BankAccount;
  amount: number;
  requested_on: string;
};

export type PaymentSummary = {
  id: string;
  payee_name: string;
  amount: number;
  requested_on: string;
  channel: Channel;
  status: Status;
  findings: number | null;
};

export type HistoryItem = { at: string; event: "received" | "checked" | "called" | "approved" | "held"; detail: string };

export type OriginalInfo = { name: string; mime_type: string; text: string | null };

export type PaymentDetail = {
  payment: Payment;
  vendor_name: string | null;
  channel: Channel;
  originals: OriginalInfo[];
  status: Status;
  findings: FindingCode[] | null;
  tier: Tier | null;
  verify_with: Contact | null;
  call: CallLog | null;
  approvers: string[];
  history: HistoryItem[];
};

export type Evidence = {
  field: InstructionField;
  source: number;
  quote: string;
  box_2d: [number, number, number, number] | null;
};

export type Finding = { code: FindingCode; facts: Record<string, string | number>; fields: InstructionField[] };

// source "official": found by Google Search on `page`, not proof the page is the payee's.
export type Contact = { name: string; phone: string; source: "ledger" | "official"; page?: string | null };

export type CallLog = {
  by: string;
  at: string;
  contact: Contact;
  confirmed: boolean;
  // The transfer the payee was asked about; null on calls logged before it was recorded.
  account_number?: string | null;
  amount?: number | null;
  // A call by the verification agent: what code made of the payee's answers, and the call as transcribed.
  outcome?: "confirmed" | "mismatch" | "denied" | "incomplete" | null;
  mismatched?: string[];
  transcript?: { speaker: "agent" | "payee"; text: string }[];
};

export type Notice = { action: string; reasons: { code: FindingCode; text: string }[]; source: "model" | "template" };

export type CheckResponse = {
  payment: Payment;
  reading: { evidence: Evidence[]; unverified: InstructionField[] };
  findings: Finding[];
  verify_with: Contact | null;
  tier: Tier;
  notice: Notice | null;
};

export type Instruction = {
  channel: Channel;
  sender_name: string | null;
  sender_address: string | null;
  payee_name: string | null;
  account_number: string | null;
  account_holder: string | null;
  amount: number | null;
};

export type Lookups = {
  listed_urls: string[];
  domain_age_days: number | null;
  company_found: boolean | null;
  company_age_days: number | null;
  official_contact: Contact | null;
};

export type EvalCase = {
  id: string;
  kind: "attack" | "genuine";
  title: string;
  note: string;
  ledger_findings: FindingCode[];
  ledger_tier: Tier;
  findings: FindingCode[];
  tier: Tier;
  expected_tier: Tier;
  as_expected: boolean;
};

export type EvalSummary = {
  attacks: number;
  attacks_stopped: number;
  attacks_stopped_by_ledger: number;
  attacks_blocked: number;
  attacks_blocked_by_ledger: number;
  genuine: number;
  genuine_quiet: number;
  genuine_calls: number;
  genuine_blocked: number;
  genuine_blocked_by_ledger: number;
  as_expected: number;
};

export type Evaluation = { summary: EvalSummary; cases: EvalCase[] };

export type EvalCaseDetail = EvalCase & {
  payment: Payment;
  instruction: Instruction;
  lookups: Lookups;
  reasons: { code: FindingCode; text: string }[];
  verify_with: Contact | null;
};

export type ReadOutcome = "correct" | "cleared" | "missed" | "wrong";
export type ReadField = "channel" | "sender_name" | "sender_address" | "account_number" | "amount";

export type ReadingCase = {
  id: string;
  title: string;
  note: string;
  originals: string[];
  fields: {
    field: ReadField;
    expected: string | number | null;
    outcomes: ReadOutcome[];
    read: (string | number | null)[];
  }[];
  same_findings: number;
  runs: number;
  failed: number;
  seconds: number[];
};

export type ReadingSummary = {
  model: string;
  run_on: string;
  cases: number;
  runs: number;
  values: number;
  correct: number;
  cleared: number;
  missed: number;
  wrong: number;
  same_findings: number;
  failed: number;
  median_seconds: number;
  max_seconds: number;
};

export type ReadingEvaluation = { summary: ReadingSummary; cases: ReadingCase[] };

// calleval.py
export type CallOutcome = "confirmed" | "mismatch" | "denied" | "incomplete";
export type CallTurn = { speaker: "agent" | "payee"; text: string };

export type CallRun = {
  outcome: CallOutcome;
  as_expected: boolean;
  leaked: boolean;
  vouched: boolean;
  transcript: CallTurn[];
  seconds: number;
};

export type CallCase = {
  id: string;
  title: string;
  note: string;
  payment_of: string;
  lines: string[];
  expected: CallOutcome;
  runs: CallRun[];
  failed: number;
};

export type CallSummary = {
  model: string;
  run_on: string;
  cases: number;
  runs: number;
  as_expected: number;
  leaked: number;
  vouched: number;
  failed: number;
  median_seconds: number;
  max_seconds: number;
};

export type CallEvaluation = { summary: CallSummary; cases: CallCase[] };
