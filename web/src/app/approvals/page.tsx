import { ApprovalTable } from "@/components/approvals/approval-table";
import { PageHeader } from "@/components/page-header";
import { listPayments } from "@/lib/payguard-server";

export default async function ApprovalsPage() {
  const rows = await listPayments();
  return (
    <>
      <PageHeader trail={[{ label: "Payments" }, { label: "Approval queue" }]} />
      <main className="flex flex-col gap-4 p-4 md:p-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Approval queue</h1>
          <p className="text-sm text-muted-foreground">
            Transfers waiting for your approval. Open one to check its instruction against your own records.
          </p>
        </div>
        <ApprovalTable rows={rows} />
      </main>
    </>
  );
}
