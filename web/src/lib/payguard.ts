// Types mirror agent/app/payguard (api.py, pipeline.py, models.py, reader.py, explain.py).

export type Channel = "email" | "line" | "sms" | "phone" | "in_person" | "edi" | "other";
export type Status = "pending" | "approved" | "held";
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
  | "NEW_DOMAIN";
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

export type HistoryItem = { at: string; event: "received" | "checked" | "approved" | "held"; detail: string };

export type OriginalInfo = { name: string; mime_type: string; text: string | null };

export type PaymentDetail = {
  payment: Payment;
  vendor_name: string | null;
  channel: Channel;
  originals: OriginalInfo[];
  status: Status;
  findings: FindingCode[] | null;
  history: HistoryItem[];
};

export type Evidence = {
  field: InstructionField;
  source: number;
  quote: string;
  box_2d: [number, number, number, number] | null;
};

export type Finding = { code: FindingCode; facts: Record<string, string | number>; fields: InstructionField[] };

export type Contact = { name: string; phone: string; source: "ledger" | "official" };

export type Notice = { action: string; reasons: { code: FindingCode; text: string }[]; source: "model" | "template" };

export type CheckResponse = {
  payment: Payment;
  reading: { evidence: Evidence[]; unverified: InstructionField[] };
  findings: Finding[];
  verify_with: Contact | null;
  notice: Notice | null;
};
