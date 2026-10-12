import { FlowWalkthrough } from "@/components/how-it-works/flow-walkthrough";
import { PageHeader } from "@/components/page-header";
import { SCENARIOS } from "@/lib/walkthrough";

export default async function HowItWorksPage(props: PageProps<"/how-it-works">) {
  const { scenario } = await props.searchParams;
  const initial = SCENARIOS.find((s) => s.id === scenario)?.id ?? SCENARIOS[0].id;
  return (
    <>
      <PageHeader trail={[{ label: "About" }, { label: "How it works" }]} />
      <main className="flex flex-col gap-4 p-4 md:p-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">How it works</h1>
          <p className="text-sm text-muted-foreground">
            Pick a payment and watch the path it takes. Every branch is a rule in code; Gemini reads, writes and looks things
            up, but never approves or blocks.
          </p>
        </div>
        <FlowWalkthrough key={initial} initial={initial} />
      </main>
    </>
  );
}
