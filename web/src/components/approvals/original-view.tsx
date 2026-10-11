"use client";

import { FIELD_LABEL } from "@/lib/format";
import type { Evidence, InstructionField, OriginalInfo } from "@/lib/payguard";

type Mark = { quote: string; label: string; flagged: boolean };

const FLAGGED = "bg-amber-200/80 ring-1 ring-amber-500";
const READ = "bg-sky-100 ring-1 ring-sky-300";

function HighlightedText({ text, marks }: { text: string; marks: Mark[] }) {
  const spans: { start: number; end: number; mark: Mark }[] = [];
  for (const mark of marks) {
    const start = text.indexOf(mark.quote);
    if (start < 0) continue;
    const end = start + mark.quote.length;
    if (spans.some((s) => start < s.end && end > s.start)) continue;
    spans.push({ start, end, mark });
  }
  spans.sort((a, b) => a.start - b.start);

  const out: React.ReactNode[] = [];
  let at = 0;
  for (const s of spans) {
    out.push(text.slice(at, s.start));
    out.push(
      <mark key={s.start} title={s.mark.label} className={`rounded-sm px-0.5 text-inherit ${s.mark.flagged ? FLAGGED : READ}`}>
        {text.slice(s.start, s.end)}
      </mark>,
    );
    at = s.end;
  }
  out.push(text.slice(at));
  return <pre className="font-sans text-sm leading-relaxed whitespace-pre-wrap">{out}</pre>;
}

function BoxedImage({ name, evidence, flagged }: { name: string; evidence: Evidence[]; flagged: Set<InstructionField> }) {
  return (
    <div className="relative mx-auto w-full max-w-[420px]">
      {/* eslint-disable-next-line @next/next/no-img-element -- served by the agent through our API, sizes vary */}
      <img src={`/api/originals/${name}`} alt={`Original: ${name}`} className="block w-full rounded-md border" />
      {evidence
        .filter((e) => e.box_2d)
        .map((e) => {
          const [ymin, xmin, ymax, xmax] = e.box_2d!;
          const isFlagged = flagged.has(e.field);
          return (
            <div
              key={`${e.field}-${ymin}-${xmin}`}
              title={FIELD_LABEL[e.field]}
              className={`absolute rounded-sm ${isFlagged ? "border-2 border-amber-500 bg-amber-300/25" : "border border-sky-400 bg-sky-200/20"}`}
              style={{ top: `${ymin / 10}%`, left: `${xmin / 10}%`, height: `${(ymax - ymin) / 10}%`, width: `${(xmax - xmin) / 10}%` }}
            >
              {isFlagged && (
                <span className="absolute top-1/2 left-full ml-1 -translate-y-1/2 rounded bg-amber-500 px-1 text-[10px] leading-4 font-medium whitespace-nowrap text-white shadow-sm">
                  {FIELD_LABEL[e.field]}
                </span>
              )}
            </div>
          );
        })}
    </div>
  );
}

export function OriginalView({
  originals,
  evidence,
  flagged,
  showAll,
}: {
  originals: OriginalInfo[];
  evidence: Evidence[];
  flagged: Set<InstructionField>;
  showAll: boolean;
}) {
  return (
    <div className="flex flex-col gap-4">
      {originals.map((o, i) => {
        const own = evidence.filter((e) => e.source === i + 1 && (showAll || flagged.has(e.field)));
        return (
          <figure key={o.name} className="flex flex-col gap-2">
            <figcaption className="text-xs text-muted-foreground">{o.name}</figcaption>
            {o.text !== null ? (
              <div className="rounded-md border bg-muted/30 p-3">
                <HighlightedText
                  text={o.text}
                  marks={own.map((e) => ({ quote: e.quote, label: FIELD_LABEL[e.field], flagged: flagged.has(e.field) }))}
                />
              </div>
            ) : (
              <BoxedImage name={o.name} evidence={own} flagged={flagged} />
            )}
          </figure>
        );
      })}
    </div>
  );
}
