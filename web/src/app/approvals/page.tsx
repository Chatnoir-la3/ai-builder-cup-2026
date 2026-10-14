import Link from "next/link";

import { ApprovalTable } from "@/components/approvals/approval-table";
import { PageHeader } from "@/components/page-header";
import { ABOUT, START_WITH } from "@/lib/demo-english";
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
        <p className="rounded-md border bg-muted/40 px-3 py-2 text-sm">
          You are approving payments at Miori Koumuten, a small builder (fictional). New here? Open{" "}
          <Link href={`/approvals/${START_WITH}`} className="font-medium underline underline-offset-2">
            {START_WITH}
          </Link>
          . {ABOUT[START_WITH]} The originals are in Japanese; each has an English translation under it.
        </p>
        <ApprovalTable rows={rows} />
      </main>
    </>
  );
}
