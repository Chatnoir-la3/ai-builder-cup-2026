"use client";

import { RotateCcw, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CHANNEL_LABEL, STATUS_CLASS, STATUS_LABEL, formatDay, formatYen } from "@/lib/format";
import type { PaymentSummary, Status } from "@/lib/payguard";

function CheckCell({ findings }: { findings: number | null }) {
  if (findings === null) return <span className="text-muted-foreground">Not checked yet</span>;
  if (findings === 0) return <span className="text-emerald-700">Nothing unusual</span>;
  return <span className="font-medium text-amber-800">{findings} to confirm</span>;
}

export function ApprovalTable({ rows }: { rows: PaymentSummary[] }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<Status | "all">("all");
  const [resetting, setResetting] = useState(false);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter(
      (r) => (status === "all" || r.status === status) && (!q || `${r.id} ${r.payee_name}`.toLowerCase().includes(q)),
    );
  }, [rows, query, status]);

  async function reset() {
    setResetting(true);
    try {
      await fetch("/api/demo/reset", { method: "POST" });
      router.refresh();
    } finally {
      setResetting(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-full max-w-[360px]">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by payee or ID"
            className="pl-8"
          />
        </div>
        <Select value={status} onValueChange={(v) => setStatus(v as Status | "all")}>
          <SelectTrigger className="w-[150px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All statuses</SelectItem>
            <SelectItem value="pending">Pending</SelectItem>
            <SelectItem value="approved">Approved</SelectItem>
            <SelectItem value="held">On hold</SelectItem>
          </SelectContent>
        </Select>
        <Button variant="outline" className="ml-auto" onClick={reset} disabled={resetting}>
          <RotateCcw />
          Reset demo
        </Button>
      </div>

      <div className="overflow-hidden rounded-lg border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[90px]">ID</TableHead>
              <TableHead>Payee</TableHead>
              <TableHead className="text-right">Amount</TableHead>
              <TableHead>Requested</TableHead>
              <TableHead>Instruction</TableHead>
              <TableHead>Check</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {shown.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="h-24 text-center text-muted-foreground">
                  No payments match. Clear the search or choose another status.
                </TableCell>
              </TableRow>
            ) : (
              shown.map((r) => (
                <TableRow
                  key={r.id}
                  className="cursor-pointer"
                  onClick={() => router.push(`/approvals/${r.id}`)}
                  onKeyDown={(e) => e.key === "Enter" && router.push(`/approvals/${r.id}`)}
                  tabIndex={0}
                >
                  <TableCell className="font-mono text-xs">{r.id}</TableCell>
                  <TableCell className="font-medium">{r.payee_name}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatYen(r.amount)}</TableCell>
                  <TableCell>{formatDay(r.requested_on)}</TableCell>
                  <TableCell>{CHANNEL_LABEL[r.channel]}</TableCell>
                  <TableCell>
                    <CheckCell findings={r.findings} />
                  </TableCell>
                  <TableCell>
                    <Badge className={STATUS_CLASS[r.status]}>{STATUS_LABEL[r.status]}</Badge>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          {shown.length} of {rows.length} payments
        </span>
        <Pagination className="mx-0 w-auto">
          <PaginationContent>
            <PaginationItem>
              <PaginationPrevious aria-disabled className="pointer-events-none opacity-50" />
            </PaginationItem>
            <PaginationItem>
              <PaginationLink isActive>1</PaginationLink>
            </PaginationItem>
            <PaginationItem>
              <PaginationNext aria-disabled className="pointer-events-none opacity-50" />
            </PaginationItem>
          </PaginationContent>
        </Pagination>
      </div>
    </div>
  );
}
