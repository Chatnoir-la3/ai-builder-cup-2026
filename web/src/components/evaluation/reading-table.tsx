import { Check } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { CHANNEL_LABEL, FIELD_LABEL, formatYen } from "@/lib/format";
import type { Channel, ReadField, ReadingCase, ReadOutcome } from "@/lib/payguard";

const COLUMNS: ReadField[] = ["channel", "sender_name", "sender_address", "account_number", "amount"];

const OUTCOME: Record<Exclude<ReadOutcome, "correct">, { label: string; className: string }> = {
  cleared: { label: "Cleared by the code check", className: "bg-amber-100 text-amber-900 hover:bg-amber-100" },
  missed: { label: "Not read", className: "bg-zinc-100 text-zinc-700 hover:bg-zinc-100" },
  wrong: { label: "Wrong value", className: "bg-red-100 text-red-800 hover:bg-red-100" },
};

function label(field: ReadField): string {
  return field === "channel" ? "Channel" : FIELD_LABEL[field];
}

function show(field: ReadField, v: string | number | null): string {
  if (v === null) return "None shown";
  if (field === "amount") return formatYen(Number(v));
  if (field === "channel") return CHANNEL_LABEL[v as Channel];
  return String(v);
}

function FieldCell({ field, f }: { field: ReadField; f: ReadingCase["fields"][number] }) {
  const runs = f.outcomes.length;
  const misses = (Object.keys(OUTCOME) as (keyof typeof OUTCOME)[])
    .map((o) => ({ o, n: f.outcomes.filter((x) => x === o).length }))
    .filter((m) => m.n > 0);
  const wrong = f.read.filter((v, i) => f.outcomes[i] === "wrong");
  return (
    <div className="flex flex-col gap-1">
      <span className={f.expected === null ? "text-muted-foreground" : ""}>{show(field, f.expected)}</span>
      {misses.length === 0 ? (
        <span className="flex items-center gap-1 text-xs text-emerald-700">
          <Check className="size-3.5" /> {runs}/{runs}
        </span>
      ) : (
        misses.map(({ o, n }) => (
          <Badge key={o} className={`w-fit font-normal ${OUTCOME[o].className}`}>
            {OUTCOME[o].label} {n}/{runs}
          </Badge>
        ))
      )}
      {wrong.length > 0 && (
        <span className="text-xs text-red-800">Read: {wrong.map((v) => show(field, v)).join(", ")}</span>
      )}
    </div>
  );
}

export function ReadingTable({ rows }: { rows: ReadingCase[] }) {
  return (
    <div className="overflow-hidden rounded-lg border bg-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[56px]">ID</TableHead>
            <TableHead>Case</TableHead>
            {COLUMNS.map((c) => (
              <TableHead key={c}>{label(c)}</TableHead>
            ))}
            <TableHead className="w-[96px]">Findings</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((r) => {
            const done = r.runs - r.failed;
            return (
              <TableRow key={r.id} className="align-top">
                <TableCell className="font-mono text-xs">{r.id}</TableCell>
                <TableCell className="max-w-[300px] whitespace-normal">
                  <div className="font-medium">{r.title}</div>
                  <div className="text-xs text-muted-foreground">{r.originals.join(" + ")}</div>
                  {r.note && <div className="mt-1 text-xs text-muted-foreground">{r.note}</div>}
                  {r.failed > 0 && (
                    <div className="mt-1 text-xs text-red-800">
                      {r.failed} of {r.runs} runs could not read the originals
                    </div>
                  )}
                </TableCell>
                {COLUMNS.map((c) => (
                  <TableCell key={c} className="max-w-[200px] text-sm break-all whitespace-normal">
                    <FieldCell field={c} f={r.fields.find((f) => f.field === c)!} />
                  </TableCell>
                ))}
                <TableCell>
                  <span
                    className={
                      r.same_findings === done
                        ? "flex items-center gap-1 text-sm text-emerald-700"
                        : "text-sm font-medium text-red-700"
                    }
                  >
                    {r.same_findings === done && <Check className="size-4" />} {r.same_findings}/{done}
                  </span>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
