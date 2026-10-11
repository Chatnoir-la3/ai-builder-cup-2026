import type { Channel, FindingCode, InstructionField, Status } from "@/lib/payguard";

const yen = new Intl.NumberFormat("en-US", { style: "currency", currency: "JPY" });
const day = new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeZone: "Asia/Tokyo" });
const dayTime = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
  timeZone: "Asia/Tokyo",
});

export const formatYen = (n: number) => yen.format(n);
export const formatDay = (iso: string) => day.format(new Date(`${iso}T00:00:00+09:00`));
export const formatDayTime = (iso: string) => dayTime.format(new Date(iso));

export const CHANNEL_LABEL: Record<Channel, string> = {
  email: "Email",
  line: "LINE",
  sms: "Text message",
  phone: "Phone",
  in_person: "In person",
  edi: "EDI",
  other: "Other",
};

export const STATUS_LABEL: Record<Status, string> = { pending: "Pending", approved: "Approved", held: "On hold" };

// admin-ui status colours: needs action = yellow, done = green, on hold = grey.
export const STATUS_CLASS: Record<Status, string> = {
  pending: "bg-amber-100 text-amber-900 hover:bg-amber-100",
  approved: "bg-emerald-100 text-emerald-900 hover:bg-emerald-100",
  held: "bg-zinc-200 text-zinc-700 hover:bg-zinc-200",
};

export const FINDING_LABEL: Record<FindingCode, string> = {
  NEW_PAYEE: "New payee",
  ACCOUNT_NOT_REGISTERED: "Unregistered account",
  ACCOUNT_RECENTLY_REGISTERED: "Recently added account",
  HOLDER_MISMATCH: "Holder name differs",
  AMOUNT_ABOVE_HISTORY: "Amount above history",
  SENDER_DOMAIN_LOOKALIKE: "Lookalike domain",
  SENDER_DOMAIN_UNREGISTERED: "Unregistered domain",
  UNUSUAL_CHANNEL: "Unusual channel",
  INSTRUCTION_MISMATCH: "Instruction mismatch",
};

export const FIELD_LABEL: Record<InstructionField, string> = {
  sender_name: "Sender",
  sender_address: "Sender address",
  payee_name: "Payee",
  account_number: "Account number",
  account_holder: "Account holder",
  amount: "Amount",
};

export const ACCOUNT_TYPE_LABEL = { ordinary: "Ordinary", current: "Current" } as const;
