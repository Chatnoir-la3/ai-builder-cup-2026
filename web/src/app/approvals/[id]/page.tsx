import { notFound } from "next/navigation";

import { PaymentReview } from "@/components/approvals/payment-review";
import { PageHeader } from "@/components/page-header";
import { getPayment } from "@/lib/payguard-server";
import { readSession } from "@/lib/session";

export default async function PaymentPage(props: PageProps<"/approvals/[id]">) {
  const { id } = await props.params;
  const detail = await getPayment(id);
  if (!detail) notFound();
  const { actingAs } = await readSession();
  return (
    <>
      <PageHeader trail={[{ label: "Approval queue", href: "/approvals" }, { label: id }]} />
      <PaymentReview initial={detail} actingAs={actingAs} />
    </>
  );
}
