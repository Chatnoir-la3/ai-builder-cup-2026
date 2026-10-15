import { Check } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { CallCase, CallOutcome } from "@/lib/payguard";

export const OUTCOME_LABEL: Record<CallOutcome, string> = {
  confirmed: "Confirmed",
  mismatch: "Different account or amount",
  denied: "No such request",
  incomplete: "Nothing confirmed",
};

function Transcript({ c }: { c: CallCase }) {
  const run = c.runs[0];
  if (!run) return null;
  return (
    <details className="mt-1">
      <summary className="cursor-pointer text-xs text-muted-foreground">Read the first call</summary>
      <ol className="mt-1 flex flex-col gap-1 text-xs">
        {run.transcript.map((t, i) => (
          <li key={i}>
            <span className="text-muted-foreground">{t.speaker === "agent" ? "Agent" : "Payee"}: </span>
            {t.text}
          </li>
        ))}
      </ol>
    </details>
  );
}

export function CallTable({ rows }: { rows: CallCase[] }) {
  return (
    <div className="overflow-hidden rounded-lg border bg-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[56px]">ID</TableHead>
            <TableHead>Case</TableHead>
            <TableHead className="w-[180px]">Expected</TableHead>
            <TableHead className="w-[220px]">What code decided, per call</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((c) => {
            const ok = c.runs.filter((r) => r.as_expected).length;
            const wrong = c.runs.filter((r) => !r.as_expected);
            const leaks = c.runs.filter((r) => r.leaked).length;
            const vouches = c.runs.filter((r) => r.vouched).length;
            return (
              <TableRow key={c.id} className="align-top">
                <TableCell className="font-mono text-xs">{c.id}</TableCell>
                <TableCell className="max-w-[520px] whitespace-normal">
                  <div className="font-medium">{c.title}</div>
                  <div className="text-xs text-muted-foreground">
                    {c.payment_of} · the payee says: {c.lines.map((l) => `“${l}”`).join(" then ")}
                  </div>
                  {c.note && <div className="mt-1 text-xs text-muted-foreground">{c.note}</div>}
                  <Transcript c={c} />
                </TableCell>
                <TableCell className="text-sm whitespace-normal">{OUTCOME_LABEL[c.expected]}</TableCell>
                <TableCell className="flex flex-col gap-1 whitespace-normal">
                  <span
                    className={
                      wrong.length === 0
                        ? "flex items-center gap-1 text-sm text-emerald-700"
                        : "text-sm font-medium text-red-700"
                    }
                  >
                    {wrong.length === 0 && <Check className="size-4" />} {ok}/{c.runs.length} as expected
                  </span>
                  {wrong.map((r, i) => (
                    <Badge key={i} className="w-fit bg-red-100 font-normal text-red-800 hover:bg-red-100">
                      {OUTCOME_LABEL[r.outcome]}
                    </Badge>
                  ))}
                  {leaks > 0 && <span className="text-xs text-red-800">Agent said the transfer first: {leaks}</span>}
                  {vouches > 0 && <span className="text-xs text-red-800">Agent said it matches: {vouches}</span>}
                  {c.failed > 0 && <span className="text-xs text-red-800">{c.failed} call(s) dropped</span>}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
