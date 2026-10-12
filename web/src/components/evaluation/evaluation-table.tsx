"use client";

import { Check, Search, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { FINDING_LABEL, TIER_CLASS, TIER_LABEL } from "@/lib/format";
import type { EvalCase, Tier } from "@/lib/payguard";

type Kind = EvalCase["kind"] | "all";

export function TierBadge({ tier }: { tier: Tier }) {
  return <Badge className={TIER_CLASS[tier]}>{TIER_LABEL[tier]}</Badge>;
}

export function EvaluationTable({ rows }: { rows: EvalCase[] }) {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<Kind>("all");

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter(
      (r) => (kind === "all" || r.kind === kind) && (!q || `${r.id} ${r.title}`.toLowerCase().includes(q)),
    );
  }, [rows, query, kind]);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative w-full max-w-[360px]">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by case or ID"
            className="pl-8"
          />
        </div>
        <Select value={kind} onValueChange={(v) => setKind(v as Kind)}>
          <SelectTrigger className="w-[170px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All cases</SelectItem>
            <SelectItem value="attack">Attacks</SelectItem>
            <SelectItem value="genuine">Genuine payments</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="overflow-hidden rounded-lg border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[64px]">ID</TableHead>
              <TableHead>Case</TableHead>
              <TableHead>Findings</TableHead>
              <TableHead>Ledger alone</TableHead>
              <TableHead>With lookups</TableHead>
              <TableHead className="w-[90px]">Expected</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {shown.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                  No cases match. Clear the search or choose another kind.
                </TableCell>
              </TableRow>
            ) : (
              shown.map((r) => (
                <TableRow
                  key={r.id}
                  className="cursor-pointer"
                  onClick={() => router.push(`/evaluation/${r.id}`)}
                  onKeyDown={(e) => e.key === "Enter" && router.push(`/evaluation/${r.id}`)}
                  tabIndex={0}
                >
                  <TableCell className="font-mono text-xs">{r.id}</TableCell>
                  <TableCell className="max-w-[360px] whitespace-normal">
                    <div className="font-medium">{r.title}</div>
                    <div className="text-xs text-muted-foreground">
                      {r.kind === "attack" ? "Attack" : "Genuine payment"}
                    </div>
                  </TableCell>
                  <TableCell className="max-w-[280px] whitespace-normal">
                    <div className="flex flex-wrap gap-1">
                      {r.findings.length === 0 ? (
                        <span className="text-sm text-muted-foreground">None</span>
                      ) : (
                        r.findings.map((f) => (
                          <Badge key={f} variant="outline" className="font-normal">
                            {FINDING_LABEL[f]}
                          </Badge>
                        ))
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <TierBadge tier={r.ledger_tier} />
                  </TableCell>
                  <TableCell>
                    <TierBadge tier={r.tier} />
                  </TableCell>
                  <TableCell>
                    {r.as_expected ? (
                      <span className="flex items-center gap-1 text-sm text-emerald-700">
                        <Check className="size-4" /> Yes
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-sm font-medium text-red-700">
                        <X className="size-4" /> No
                      </span>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <div className="text-sm text-muted-foreground">
        {shown.length} of {rows.length} cases
      </div>
    </div>
  );
}
