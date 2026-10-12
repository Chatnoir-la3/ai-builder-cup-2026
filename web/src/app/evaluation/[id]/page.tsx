import Link from "next/link";
import { notFound } from "next/navigation";

import { TierBadge } from "@/components/evaluation/evaluation-table";
import { PageHeader } from "@/components/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ACCOUNT_TYPE_LABEL, CHANNEL_LABEL, FINDING_LABEL, formatYen } from "@/lib/format";
import type { FindingCode, Lookups } from "@/lib/payguard";
import { getEvalCase } from "@/lib/payguard-server";

function Item({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[150px_1fr] gap-3 py-2 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="break-all">{children}</dd>
    </div>
  );
}

function Codes({ codes }: { codes: FindingCode[] }) {
  if (codes.length === 0) return <span className="text-muted-foreground">None</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {codes.map((c) => (
        <Badge key={c} variant="outline" className="font-normal">
          {FINDING_LABEL[c]}
        </Badge>
      ))}
    </div>
  );
}

function lookupRows(l: Lookups): [string, string][] {
  const rows: [string, string][] = [];
  if (l.listed_urls.length) rows.push(["Web Risk lists", l.listed_urls.join(", ")]);
  if (l.domain_age_days !== null) rows.push(["Sender domain age", `${l.domain_age_days} days`]);
  if (l.company_found !== null) rows.push(["In company registry", l.company_found ? "Yes" : "No"]);
  if (l.company_age_days !== null) rows.push(["Company age", `${l.company_age_days} days`]);
  if (l.official_contact)
    rows.push(["Official number found", `${l.official_contact.phone} (${l.official_contact.name})`]);
  return rows;
}

export default async function EvalCasePage(props: PageProps<"/evaluation/[id]">) {
  const { id } = await props.params;
  const c = await getEvalCase(id);
  if (!c) notFound();
  const { payment: p, instruction: ins } = c;
  const lookups = lookupRows(c.lookups);
  const added = c.findings.filter((f) => !c.ledger_findings.includes(f));

  return (
    <>
      <PageHeader trail={[{ label: "Evaluation", href: "/evaluation" }, { label: id }]} />
      <main className="flex flex-col gap-4 p-4 md:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-semibold tracking-tight">{c.title}</h1>
              <TierBadge tier={c.tier} />
            </div>
            <p className="text-sm text-muted-foreground">
              {c.id} · {c.kind === "attack" ? "Attack" : "Genuine payment"} · expected {c.expected_tier},{" "}
              {c.as_expected ? "as expected" : "not as expected"}
            </p>
          </div>
          <Button variant="outline" asChild>
            <Link href="/evaluation">Back to evaluation</Link>
          </Button>
        </div>

        <div className="grid gap-4 lg:grid-cols-3">
          <div className="flex flex-col gap-4 lg:col-span-2">
            <Card>
              <CardHeader>
                <CardTitle>Payment</CardTitle>
                <CardDescription>As entered in internet banking.</CardDescription>
              </CardHeader>
              <CardContent>
                <dl className="divide-y">
                  <Item label="Payee">
                    {p.payee_name}
                    {!p.vendor_id && <span className="text-muted-foreground"> (not in the vendor list)</span>}
                  </Item>
                  <Item label="Account">
                    {p.account.bank_name} {p.account.branch_name} · {ACCOUNT_TYPE_LABEL[p.account.account_type]}{" "}
                    {p.account.number}
                  </Item>
                  <Item label="Account holder">{p.account.holder_kana}</Item>
                  <Item label="Amount">
                    <span className="tabular-nums">{formatYen(p.amount)}</span>
                  </Item>
                </dl>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Instruction</CardTitle>
                <CardDescription>What the instruction says, as the reader would return it.</CardDescription>
              </CardHeader>
              <CardContent>
                <dl className="divide-y">
                  <Item label="Channel">{CHANNEL_LABEL[ins.channel]}</Item>
                  <Item label="Sender">{[ins.sender_name, ins.sender_address].filter(Boolean).join(" · ") || "—"}</Item>
                  {ins.account_number && <Item label="Account">{ins.account_number}</Item>}
                  {ins.amount !== null && <Item label="Amount">{formatYen(ins.amount)}</Item>}
                </dl>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Lookups</CardTitle>
                <CardDescription>Given for this case: what each source would return.</CardDescription>
              </CardHeader>
              <CardContent>
                {lookups.length === 0 ? (
                  <p className="text-sm text-muted-foreground">Nothing beyond the ledger.</p>
                ) : (
                  <dl className="divide-y">
                    {lookups.map(([k, v]) => (
                      <Item key={k} label={k}>
                        {v}
                      </Item>
                    ))}
                  </dl>
                )}
              </CardContent>
            </Card>
          </div>

          <div className="flex flex-col gap-4">
            <Card>
              <CardHeader>
                <CardTitle>Why</CardTitle>
                <CardDescription>The rules&apos; findings, in the approver&apos;s words.</CardDescription>
              </CardHeader>
              <CardContent className="flex flex-col gap-4 text-sm">
                {c.reasons.length === 0 ? (
                  <p className="text-muted-foreground">Nothing differs from the ledger: it is approved as usual.</p>
                ) : (
                  <ul className="flex list-disc flex-col gap-1.5 pl-5">
                    {c.reasons.map((r) => (
                      <li key={r.code}>{r.text}</li>
                    ))}
                  </ul>
                )}
                {c.verify_with && (
                  <div className="rounded-md border p-3">
                    <div className="text-xs text-muted-foreground">
                      Call {c.verify_with.source === "official" ? "the payee's official number" : "the ledger contact"}
                    </div>
                    <div className="font-medium tabular-nums">{c.verify_with.phone}</div>
                    <div>{c.verify_with.name}</div>
                  </div>
                )}
                {c.note && <p className="text-muted-foreground">{c.note}</p>}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Outcome</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-3 text-sm">
                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">Ledger alone</span>
                    <TierBadge tier={c.ledger_tier} />
                  </div>
                  <Codes codes={c.ledger_findings} />
                </div>
                <div className="flex flex-col gap-1.5 border-t pt-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">With lookups</span>
                    <TierBadge tier={c.tier} />
                  </div>
                  {added.length > 0 ? (
                    <>
                      <span className="text-xs text-muted-foreground">Added by the lookups</span>
                      <Codes codes={added} />
                    </>
                  ) : (
                    <span className="text-muted-foreground">The lookups add no findings.</span>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </>
  );
}
