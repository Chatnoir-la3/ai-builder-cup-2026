"use client";

import { AlertTriangle, CheckCircle2, Phone, RotateCw } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { OriginalView } from "@/components/approvals/original-view";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  ACCOUNT_TYPE_LABEL,
  CHANNEL_LABEL,
  FIELD_LABEL,
  FINDING_LABEL,
  STATUS_CLASS,
  STATUS_LABEL,
  formatDay,
  formatDayTime,
  formatYen,
} from "@/lib/format";
import type { CheckResponse, FindingCode, HistoryItem, InstructionField, PaymentDetail } from "@/lib/payguard";

type CheckState =
  | { state: "running" }
  | { state: "done"; result: CheckResponse }
  | { state: "error"; message: string }
  | { state: "skipped" };

const EVENT_LABEL: Record<HistoryItem["event"], string> = {
  received: "Received",
  checked: "Checked",
  approved: "Approved",
  held: "Put on hold",
};

// Which rows of the payment card a finding is about.
const ROW_CODES: Record<string, FindingCode[]> = {
  payee: ["NEW_PAYEE"],
  account: ["ACCOUNT_NOT_REGISTERED", "ACCOUNT_RECENTLY_REGISTERED", "INSTRUCTION_MISMATCH"],
  holder: ["HOLDER_MISMATCH"],
  amount: ["AMOUNT_ABOVE_HISTORY", "INSTRUCTION_MISMATCH"],
};

function Row({ label, flagged, children }: { label: string; flagged?: boolean; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[140px_1fr] gap-3 py-2 text-sm">
      <dt className={flagged ? "font-medium text-amber-800" : "text-muted-foreground"}>
        {flagged && <span className="mr-1.5 inline-block size-1.5 rounded-full bg-amber-500 align-middle" />}
        {label}
      </dt>
      <dd className={flagged ? "font-medium" : undefined}>{children}</dd>
    </div>
  );
}

function History({ items }: { items: HistoryItem[] }) {
  return (
    <ol className="flex flex-col gap-3">
      {[...items].reverse().map((h) => (
        <li key={`${h.at}-${h.event}`} className="grid grid-cols-[88px_1fr] gap-2 text-sm">
          <time className="text-muted-foreground tabular-nums">{formatDayTime(h.at)}</time>
          <div>
            <div className="font-medium">{EVENT_LABEL[h.event]}</div>
            {h.detail && <div className="text-muted-foreground">{h.detail}</div>}
          </div>
        </li>
      ))}
    </ol>
  );
}

function NoticeCard({
  check,
  confirmed,
  onConfirm,
  onRetry,
  status,
}: {
  check: CheckState;
  confirmed: boolean;
  onConfirm: (v: boolean) => void;
  onRetry: () => void;
  status: PaymentDetail["status"];
}) {
  if (status !== "pending" || check.state === "skipped") {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Decision recorded</CardTitle>
          <CardDescription>This payment is {STATUS_LABEL[status].toLowerCase()}. See the history for details.</CardDescription>
        </CardHeader>
      </Card>
    );
  }
  if (check.state === "running") {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Checking…</CardTitle>
          <CardDescription>
            Gemini is reading the original. Code then compares it with your vendor ledger and past payments.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          <Skeleton className="h-4 w-11/12" />
          <Skeleton className="h-4 w-9/12" />
          <Skeleton className="h-4 w-10/12" />
        </CardContent>
      </Card>
    );
  }
  if (check.state === "error") {
    return (
      <Alert variant="destructive">
        <AlertTriangle />
        <AlertTitle>The check could not run</AlertTitle>
        <AlertDescription className="flex flex-col items-start gap-2">
          <span>{check.message}</span>
          <Button size="sm" variant="outline" onClick={onRetry}>
            <RotateCw />
            Try again
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  const { result } = check;
  const unverified = result.reading.unverified;
  if (!result.notice) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-emerald-800">
            <CheckCircle2 className="size-5" />
            Nothing differs from your usual pattern
          </CardTitle>
          <CardDescription>Compared with your vendor ledger and payment history.</CardDescription>
        </CardHeader>
        {unverified.length > 0 && (
          <CardContent className="text-sm text-muted-foreground">
            Not confirmed in the original: {unverified.map((f) => FIELD_LABEL[f]).join(", ")}
          </CardContent>
        )}
      </Card>
    );
  }

  const { notice, verify_with: contact } = result;
  return (
    <Card className="border-amber-300 bg-amber-50/60">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-amber-900">
          <AlertTriangle className="size-5" />
          Check before you approve
        </CardTitle>
        <CardDescription className="text-base font-medium text-foreground">{notice.action}</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <ul className="flex list-disc flex-col gap-1.5 pl-5 text-sm">
          {notice.reasons.map((r) => (
            <li key={r.code}>{r.text}</li>
          ))}
        </ul>

        {contact && (
          <div className="rounded-md border bg-background p-3">
            <div className="text-xs text-muted-foreground">From your vendor ledger, not from the message</div>
            <div className="mt-1 flex items-center gap-2 font-medium">
              <Phone className="size-4" />
              <a href={`tel:${contact.phone}`} className="tabular-nums underline-offset-2 hover:underline">
                {contact.phone}
              </a>
            </div>
            <div className="text-sm">{contact.name}</div>
          </div>
        )}

        <label className="flex cursor-pointer items-start gap-2 text-sm">
          <Checkbox checked={confirmed} onCheckedChange={(v) => onConfirm(v === true)} className="mt-0.5" />
          <span>
            I called {contact ? contact.name : "a contact I already know"} and confirmed this payment.
          </span>
        </label>

        <div className="flex flex-wrap gap-1.5">
          {result.findings.map((f) => (
            <Badge key={f.code} variant="outline" className="border-amber-300 bg-background text-amber-900">
              {FINDING_LABEL[f.code]}
            </Badge>
          ))}
        </div>

        <p className="text-xs text-muted-foreground">
          {notice.source === "model"
            ? "Wording by Gemini, checked against the findings by code."
            : "Standard wording: Gemini's text did not pass the checks."}{" "}
          Nothing is blocked; you decide.
          {unverified.length > 0 && <> Not confirmed in the original: {unverified.map((f) => FIELD_LABEL[f]).join(", ")}.</>}
        </p>
      </CardContent>
    </Card>
  );
}

export function PaymentReview({ initial }: { initial: PaymentDetail }) {
  const router = useRouter();
  const { payment, status } = initial;
  const [check, setCheck] = useState<CheckState>(status === "pending" ? { state: "running" } : { state: "skipped" });
  const [confirmed, setConfirmed] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [deciding, setDeciding] = useState(false);
  const [decisionError, setDecisionError] = useState<string | null>(null);
  const started = useRef(false);

  const runCheck = useCallback(async () => {
    setCheck({ state: "running" });
    try {
      const res = await fetch(`/api/payments/${payment.id}/check`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "The check could not run.");
      setCheck({ state: "done", result: data as CheckResponse });
      router.refresh();
    } catch (e) {
      setCheck({ state: "error", message: e instanceof Error ? e.message : "The check could not run." });
    }
  }, [payment.id, router]);

  useEffect(() => {
    if (started.current || status !== "pending") return;
    started.current = true;
    void runCheck();
  }, [runCheck, status]);

  async function decide(decision: "approved" | "held") {
    setDeciding(true);
    setDecisionError(null);
    try {
      const res = await fetch(`/api/payments/${payment.id}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision, callback_confirmed: confirmed }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "The decision was not saved.");
      router.refresh();
    } catch (e) {
      setDecisionError(e instanceof Error ? e.message : "The decision was not saved.");
    } finally {
      setDeciding(false);
    }
  }

  const result = check.state === "done" ? check.result : null;
  const codes = new Set(result?.findings.map((f) => f.code) ?? []);
  const flaggedFields = new Set<InstructionField>(result?.findings.flatMap((f) => f.fields) ?? []);
  const rowFlagged = (row: keyof typeof ROW_CODES) => ROW_CODES[row].some((c) => codes.has(c));
  const needsCallback = (result?.findings.length ?? 0) > 0;
  const canApprove = status === "pending" && check.state === "done" && (!needsCallback || confirmed) && !deciding;

  return (
    <main className="flex flex-col gap-4 p-4 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight">{payment.payee_name}</h1>
            <Badge className={STATUS_CLASS[status]}>{STATUS_LABEL[status]}</Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            {formatYen(payment.amount)} · requested {formatDay(payment.requested_on)} · instruction by{" "}
            {CHANNEL_LABEL[initial.channel]}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" asChild>
            <Link href="/approvals">Back to queue</Link>
          </Button>
          <Button variant="outline" disabled={status !== "pending" || deciding} onClick={() => decide("held")}>
            Hold
          </Button>
          <Button disabled={!canApprove} onClick={() => decide("approved")}>
            Approve
          </Button>
        </div>
      </div>
      {decisionError && (
        <Alert variant="destructive">
          <AlertTriangle />
          <AlertTitle>{decisionError}</AlertTitle>
        </Alert>
      )}

      <Tabs defaultValue="review">
        <TabsList>
          <TabsTrigger value="review">Review</TabsTrigger>
          <TabsTrigger value="history">History</TabsTrigger>
        </TabsList>

        <TabsContent value="review" className="mt-2">
          <div className="grid gap-4 lg:grid-cols-3">
            <div className="flex flex-col gap-4 lg:col-span-2">
              <Card>
                <CardHeader>
                  <CardTitle>Payment</CardTitle>
                  <CardDescription>As entered in internet banking, waiting for approval.</CardDescription>
                </CardHeader>
                <CardContent>
                  <dl className="divide-y">
                    <Row label="Payee" flagged={rowFlagged("payee")}>
                      {payment.payee_name}
                    </Row>
                    <Row label="In vendor ledger" flagged={rowFlagged("payee")}>
                      {initial.vendor_name ?? "Not in your vendor list"}
                    </Row>
                    <Row label="Bank" flagged={rowFlagged("account")}>
                      {payment.account.bank_name} {payment.account.branch_name}
                    </Row>
                    <Row label="Account" flagged={rowFlagged("account")}>
                      <span className="tabular-nums">
                        {ACCOUNT_TYPE_LABEL[payment.account.account_type]} {payment.account.number}
                      </span>
                    </Row>
                    <Row label="Account holder" flagged={rowFlagged("holder")}>
                      {payment.account.holder_kana}
                    </Row>
                    <Row label="Amount" flagged={rowFlagged("amount")}>
                      <span className="tabular-nums">{formatYen(payment.amount)}</span>
                    </Row>
                    <Row label="Requested">{formatDay(payment.requested_on)}</Row>
                  </dl>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Original instruction</CardTitle>
                  <CardDescription>
                    {!result
                      ? "The instruction as it arrived."
                      : result.findings.length > 0
                        ? "Marked where the instruction differs from your records."
                        : "Nothing in it differs from your records."}
                  </CardDescription>
                  {result && result.reading.evidence.length > 0 && (
                    <label className="flex cursor-pointer items-center gap-2 pt-1 text-sm">
                      <Checkbox checked={showAll} onCheckedChange={(v) => setShowAll(v === true)} />
                      Show everything Gemini read
                    </label>
                  )}
                </CardHeader>
                <CardContent>
                  <OriginalView
                    originals={initial.originals}
                    evidence={result?.reading.evidence ?? []}
                    flagged={flaggedFields}
                    showAll={showAll}
                  />
                </CardContent>
              </Card>
            </div>

            <div className="flex flex-col gap-4">
              <NoticeCard check={check} confirmed={confirmed} onConfirm={setConfirmed} onRetry={runCheck} status={status} />
              <Card>
                <CardHeader>
                  <CardTitle>Recent activity</CardTitle>
                </CardHeader>
                <CardContent>
                  <History items={initial.history.slice(-4)} />
                </CardContent>
              </Card>
            </div>
          </div>
        </TabsContent>

        <TabsContent value="history" className="mt-2">
          <Card>
            <CardHeader>
              <CardTitle>History</CardTitle>
              <CardDescription>Decisions are recorded with the finding codes only, not the originals.</CardDescription>
            </CardHeader>
            <CardContent>
              <History items={initial.history} />
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </main>
  );
}
