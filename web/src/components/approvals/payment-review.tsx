"use client";

import { AlertTriangle, Ban, CheckCircle2, Phone, RotateCw } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { OriginalView } from "@/components/approvals/original-view";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
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
import { cn } from "@/lib/utils";
import type { CheckResponse, FindingCode, HistoryItem, InstructionField, PaymentDetail } from "@/lib/payguard";

type CheckState =
  | { state: "running" }
  | { state: "done"; result: CheckResponse }
  | { state: "error"; message: string }
  | { state: "skipped" };

const EVENT_LABEL: Record<HistoryItem["event"], string> = {
  received: "Received",
  checked: "Checked",
  called: "Called",
  approved: "Approved",
  held: "Put on hold",
};

// Which rows of the payment card a finding is about.
const ROW_CODES: Record<string, FindingCode[]> = {
  payee: ["NEW_PAYEE", "COMPANY_NOT_FOUND", "NEW_COMPANY"],
  account: ["ACCOUNT_NOT_REGISTERED", "ACCOUNT_RECENTLY_REGISTERED", "ACCOUNT_UNVERIFIED", "INSTRUCTION_MISMATCH"],
  holder: ["HOLDER_MISMATCH", "HOLDER_NOT_COMPANY"],
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

function PersonSelect({
  value,
  people,
  placeholder,
  disabled,
  onChange,
}: {
  value: string;
  people: string[];
  placeholder: string;
  disabled?: boolean;
  onChange: (v: string) => void;
}) {
  return (
    <Select value={value} onValueChange={onChange} disabled={disabled}>
      <SelectTrigger className="w-full bg-background">
        <SelectValue placeholder={placeholder} />
      </SelectTrigger>
      <SelectContent>
        {people.map((p) => (
          <SelectItem key={p} value={p}>
            {p}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function NoticeCard({
  check,
  detail,
  actingAs,
  busy,
  onActingAs,
  onLogCall,
  onRetry,
}: {
  check: CheckState;
  detail: PaymentDetail;
  actingAs: string;
  busy: boolean;
  onActingAs: (v: string) => void;
  onLogCall: (confirmed: boolean) => void;
  onRetry: () => void;
}) {
  const { status, call } = detail;
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
  const blocked = result.tier === "block";
  const reasons = (
    <>
      <ul className="flex list-disc flex-col gap-1.5 pl-5 text-sm">
        {notice.reasons.map((r) => (
          <li key={r.code}>{r.text}</li>
        ))}
      </ul>
      <div className="flex flex-wrap gap-1.5">
        {result.findings.map((f) => (
          <Badge
            key={f.code}
            variant="outline"
            className={cn("bg-background", blocked ? "border-red-300 text-red-900" : "border-amber-300 text-amber-900")}
          >
            {FINDING_LABEL[f.code]}
          </Badge>
        ))}
      </div>
    </>
  );
  const wording =
    notice.source === "model"
      ? "Wording by Gemini, checked against the findings by code."
      : "Standard wording: Gemini's text did not pass the checks.";
  const unread = unverified.length > 0 && (
    <> Not confirmed in the original: {unverified.map((f) => FIELD_LABEL[f]).join(", ")}.</>
  );

  if (blocked) {
    return (
      <Card className="border-red-300 bg-red-50/60">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-red-900">
            <Ban className="size-5" />
            Cannot be approved
          </CardTitle>
          <CardDescription className="text-base font-medium text-foreground">{notice.action}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {reasons}
          <p className="text-xs text-muted-foreground">
            {wording} Your rules decide this, not Gemini. Put it on hold.{unread}
          </p>
        </CardContent>
      </Card>
    );
  }

  const confirmed = call?.confirmed === true;
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
        {reasons}

        {contact && (
          <div className="rounded-md border bg-background p-3">
            <div className="text-xs text-muted-foreground">
              {contact.source === "official" ? "Found by Google Search" : "From your vendor ledger"}, not from the message
            </div>
            <div className="mt-1 flex items-center gap-2 font-medium">
              <Phone className="size-4" />
              <a href={`tel:${contact.phone}`} className="tabular-nums underline-offset-2 hover:underline">
                {contact.phone}
              </a>
            </div>
            <div className="text-sm">{contact.name}</div>
            {contact.source === "official" && contact.page && (
              <div className="mt-1 text-xs break-all text-muted-foreground">
                On{" "}
                <a href={contact.page} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">
                  {contact.page}
                </a>
                . Check that this page belongs to the payee before you call.
              </div>
            )}
          </div>
        )}

        <div className="flex flex-col gap-2">
          <div className="text-sm font-medium">Who you are, in this browser</div>
          <PersonSelect value={actingAs} people={detail.approvers} placeholder="Choose who you are" onChange={onActingAs} />
        </div>

        <div className="flex flex-col gap-2">
          <div className="text-sm font-medium">1. Call and record the answer</div>
          {confirmed ? (
            <div className="flex items-center gap-2 text-sm text-emerald-800">
              <CheckCircle2 className="size-4" />
              {call.by} called at {formatDayTime(call.at)}: confirmed
              {call.account_number && call.amount != null && (
                <>
                  {" "}
                  account {call.account_number}, {formatYen(call.amount)}
                </>
              )}
            </div>
          ) : (
            <>
              <div className="text-sm text-muted-foreground">
                Ask them to confirm account {detail.payment.account.number} and {formatYen(detail.payment.amount)}.
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  className="bg-background"
                  disabled={!actingAs || busy}
                  onClick={() => onLogCall(true)}
                >
                  They confirmed it
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="bg-background"
                  disabled={!actingAs || busy}
                  onClick={() => onLogCall(false)}
                >
                  They did not
                </Button>
              </div>
            </>
          )}
        </div>

        <div className="flex flex-col gap-2">
          <div className="text-sm font-medium">2. Second approval, by someone else</div>
          <p className="text-sm text-muted-foreground">
            {!confirmed
              ? "After a confirmed call, someone other than the caller approves."
              : actingAs === call.by
                ? `You made the call. ${call.by} cannot also approve: open this payment in a private window or another browser, choose someone else, and approve there.`
                : `Approve as ${actingAs}. It must be a different browser from the one the call was logged in.`}
          </p>
        </div>

        <p className="text-xs text-muted-foreground">
          {wording} Your rules need a recorded call and a second approver.{unread}
        </p>
      </CardContent>
    </Card>
  );
}

export function PaymentReview({ initial, actingAs: initialActingAs }: { initial: PaymentDetail; actingAs: string | null }) {
  const router = useRouter();
  const { payment, status } = initial;
  const [check, setCheck] = useState<CheckState>(status === "pending" ? { state: "running" } : { state: "skipped" });
  const [actingAs, setActingAs] = useState(initialActingAs ?? "");
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

  async function post(path: "decision" | "call", body: object) {
    setDeciding(true);
    setDecisionError(null);
    try {
      const res = await fetch(`/api/payments/${payment.id}/${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "It was not saved.");
      router.refresh();
    } catch (e) {
      setDecisionError(e instanceof Error ? e.message : "It was not saved.");
    } finally {
      setDeciding(false);
    }
  }

  const decide = (decision: "approved" | "held") => post("decision", { decision });

  async function chooseActingAs(name: string) {
    setActingAs(name);
    const res = await fetch("/api/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ actingAs: name }),
    }).catch(() => null);
    if (!res?.ok) setDecisionError("Who you are was not saved.");
    else router.refresh();
  }

  const result = check.state === "done" ? check.result : null;
  const codes = new Set(result?.findings.map((f) => f.code) ?? []);
  const flaggedFields = new Set<InstructionField>(result?.findings.flatMap((f) => f.fields) ?? []);
  const flaggedDomains =
    result?.findings.flatMap((f) => (f.code.startsWith("SENDER_DOMAIN") && typeof f.facts.domain === "string" ? [f.facts.domain] : [])) ?? [];
  const rowFlagged = (row: keyof typeof ROW_CODES) => ROW_CODES[row].some((c) => codes.has(c));
  const call = initial.call;
  // After a call is logged, a later check cannot lower the tier (the agent keeps the earlier one).
  const rank = { pass: 0, verify: 1, block: 2 } as const;
  const tier =
    result && call && initial.tier && rank[initial.tier] > rank[result.tier] ? initial.tier : result?.tier;
  const ready =
    tier === "pass" || (tier === "verify" && call?.confirmed === true && actingAs !== "" && actingAs !== call.by);
  const canApprove = status === "pending" && ready && !deciding;

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
                    flaggedDomains={flaggedDomains}
                    showAll={showAll}
                  />
                </CardContent>
              </Card>
            </div>

            <div className="flex flex-col gap-4">
              <NoticeCard
                check={check}
                detail={initial}
                actingAs={actingAs}
                busy={deciding}
                onActingAs={chooseActingAs}
                onLogCall={(confirmed) => post("call", { confirmed })}
                onRetry={runCheck}
              />
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
