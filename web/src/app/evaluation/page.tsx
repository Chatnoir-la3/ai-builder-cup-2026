import { EvaluationTable } from "@/components/evaluation/evaluation-table";
import { ReadingTable } from "@/components/evaluation/reading-table";
import { PageHeader } from "@/components/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getEvaluation, getReadingEvaluation } from "@/lib/payguard-server";

function Results({
  title,
  description,
  rows,
}: {
  title: string;
  description: React.ReactNode;
  rows: [string, string, string][];
}) {
  return (
    <Card className="gap-3 py-4">
      <CardHeader className="px-4">
        <CardTitle className="text-base">{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent className="px-4">
        <div className="overflow-hidden rounded-lg border">
          <Table>
            <TableBody>
              {rows.map(([label, value, note]) => (
                <TableRow key={label}>
                  <TableCell className="whitespace-normal">
                    <div>{label}</div>
                    {note && <div className="text-xs text-muted-foreground">{note}</div>}
                  </TableCell>
                  <TableCell className="w-[1%] text-right whitespace-nowrap tabular-nums">{value}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}

export default async function EvaluationPage(props: PageProps<"/evaluation">) {
  const { tab } = await props.searchParams;
  const [{ summary: s, cases }, reading] = await Promise.all([getEvaluation(), getReadingEvaluation()]);
  const r = reading.summary;
  const done = r.runs - r.failed;
  const genuineByLedger = (tier: string) => cases.filter((c) => c.kind === "genuine" && c.ledger_tier === tier).length;
  const rows: {
    label: string;
    ledger: string;
    lookups: string;
    better?: boolean;
  }[] = [
    {
      label: "Attacks stopped (not approved as usual)",
      ledger: `${s.attacks_stopped_by_ledger} / ${s.attacks}`,
      lookups: `${s.attacks_stopped} / ${s.attacks}`,
    },
    {
      label: "Attacks that cannot be approved at all",
      ledger: `${s.attacks_blocked_by_ledger}`,
      lookups: `${s.attacks_blocked}`,
    },
    {
      label: "Genuine payments wrongly blocked",
      ledger: `${s.genuine_blocked_by_ledger} / ${s.genuine}`,
      lookups: `${s.genuine_blocked} / ${s.genuine}`,
      better: s.genuine_blocked < s.genuine_blocked_by_ledger,
    },
    {
      label: "Genuine payments that need a call",
      ledger: `${genuineByLedger("verify")} / ${s.genuine}`,
      lookups: `${s.genuine_calls} / ${s.genuine}`,
    },
    {
      label: "Genuine payments approved as usual",
      ledger: `${genuineByLedger("pass")} / ${s.genuine}`,
      lookups: `${s.genuine_quiet} / ${s.genuine}`,
    },
  ];
  return (
    <>
      <PageHeader trail={[{ label: "About" }, { label: "Evaluation" }]} />
      <main className="flex flex-col gap-4 p-4 md:p-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Evaluation</h1>
          <p className="text-sm text-muted-foreground">
            How well Gemini reads the originals, and what the rules decide on what it reads.
          </p>
        </div>

        <Tabs defaultValue={tab === "reading" ? "reading" : "rules"} className="gap-4">
          <TabsList>
            <TabsTrigger value="rules">Rules · {cases.length} cases</TabsTrigger>
            <TabsTrigger value="reading">Reading by Gemini · {r.cases} cases</TabsTrigger>
          </TabsList>

          <TabsContent value="reading" className="flex flex-col gap-4">
            <Results
              title="Results"
              description={
                <>
                  Gemini ({r.model}) read each case&apos;s originals {done / r.cases} times on {r.run_on}. Scored are
                  the five values the rules use, after the code check that keeps a value only when the original shows
                  it.
                </>
              }
              rows={[
                ["Values correct", `${r.correct} / ${r.values}`, ""],
                [
                  "Wrong values that reached the rules",
                  `${r.wrong}`,
                  "The one that matters: a misread the rules would act on.",
                ],
                [
                  "Values cleared by the code check",
                  `${r.cleared}`,
                  "The original did not support the value, so the rules saw nothing and the approver is told.",
                ],
                ["Values not read", `${r.missed}`, ""],
                ["Runs where the rules reach the expected findings", `${r.same_findings} / ${done}`, ""],
                [
                  "Reading time",
                  `${r.median_seconds} s median`,
                  `Longest ${r.max_seconds} s. ${r.failed} of ${r.runs} runs failed.`,
                ],
              ]}
            />
            <ReadingTable rows={reading.cases} />
          </TabsContent>

          <TabsContent value="rules" className="flex flex-col gap-4">
            <p className="text-sm text-muted-foreground">
              {s.attacks} attacks and {s.genuine} genuine payments, run through the same rules as the approval queue.
              Open a case to see why it was stopped.
            </p>
            <Card className="gap-3 py-4">
              <CardHeader className="px-4">
                <CardTitle className="text-base">Results</CardTitle>
                <CardDescription>
                  {s.as_expected} of {cases.length} cases give the expected findings and outcome. Lookups are Web Risk,
                  the company registry, domain age and the payee&apos;s official number; here they are given per case,
                  so the result is the rules&apos; alone and repeatable.
                </CardDescription>
              </CardHeader>
              <CardContent className="px-4">
                <div className="overflow-hidden rounded-lg border">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead />
                        <TableHead className="w-[140px] text-right">Ledger alone</TableHead>
                        <TableHead className="w-[140px] text-right">With lookups</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {rows.map((r) => (
                        <TableRow key={r.label}>
                          <TableCell>{r.label}</TableCell>
                          <TableCell className="text-right tabular-nums text-muted-foreground">{r.ledger}</TableCell>
                          <TableCell
                            className={
                              r.better
                                ? "text-right font-semibold text-emerald-700 tabular-nums"
                                : "text-right tabular-nums"
                            }
                          >
                            {r.lookups}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>

            <EvaluationTable rows={cases} />
          </TabsContent>
        </Tabs>
      </main>
    </>
  );
}
