import { connection } from "next/server";

import { agentFetch } from "@/lib/agent";
import type { PaymentDetail, PaymentSummary } from "@/lib/payguard";

export async function listPayments(): Promise<PaymentSummary[]> {
  await connection();
  const res = await agentFetch("/demo/payments");
  if (!res.ok) throw new Error(`agent responded ${res.status}`);
  return res.json();
}

export async function getPayment(id: string): Promise<PaymentDetail | null> {
  await connection();
  const res = await agentFetch(`/demo/payments/${encodeURIComponent(id)}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`agent responded ${res.status}`);
  return res.json();
}
