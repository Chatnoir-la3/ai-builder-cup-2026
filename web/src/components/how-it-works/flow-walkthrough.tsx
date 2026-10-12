"use client";

import "@xyflow/react/dist/style.css";

import { Background, Handle, MarkerType, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import { RotateCcw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { EDGES, NODES, SCENARIOS, type FlowNode, type Role, type Tone, walk } from "@/lib/walkthrough";

const STEP_MS = 700;

type State = "idle" | "done" | "current" | "off";
type Data = { node: FlowNode; state: State };

const ROLE: Record<Role, string> = {
  data: "border-zinc-300 bg-white",
  ai: "border-blue-400 bg-blue-50",
  code: "border-zinc-400 bg-zinc-100",
  human: "border-amber-400 bg-amber-50",
};
const TONE: Record<Tone, string> = {
  ok: "border-green-500 bg-green-50 text-green-900",
  stop: "border-red-500 bg-red-50 text-red-900",
  hold: "border-orange-500 bg-orange-50 text-orange-900",
};
const ROLE_NAME: Record<Role, string> = { data: "Bank data", ai: "Gemini: reads, writes, looks up", code: "Code: compares and decides", human: "People: call and approve" };

const STATE = {
  idle: "",
  done: "ring-2 ring-zinc-900",
  current: "ring-4 ring-zinc-900 shadow-lg scale-[1.03]",
  off: "opacity-35",
} satisfies Record<State, string>;

function Handles() {
  return (
    <>
      <Handle type="target" id="t-top" position={Position.Top} className="!opacity-0" />
      <Handle type="source" id="s-bottom" position={Position.Bottom} className="!opacity-0" />
      {(["left", "right"] as const).map((side) => (
        <span key={side}>
          <Handle type="target" id={`t-${side}`} position={side === "left" ? Position.Left : Position.Right} className="!opacity-0" />
          <Handle type="source" id={`s-${side}`} position={side === "left" ? Position.Left : Position.Right} className="!opacity-0" />
        </span>
      ))}
    </>
  );
}

function Planned({ node }: { node: FlowNode }) {
  if (node.built) return null;
  return (
    <span className="absolute -top-2 -right-2 rounded-full border border-dashed border-zinc-400 bg-white px-1.5 text-[10px] leading-4 text-zinc-500">
      planned
    </span>
  );
}

function BoxNode({ data }: NodeProps<Node<Data>>) {
  const { node, state } = data;
  const color = node.kind === "end" ? TONE[node.tone] : node.kind === "step" ? ROLE[node.role] : "";
  const width = node.kind === "end" ? "w-[240px]" : "w-[280px]";
  return (
    <div className={cn("relative rounded-lg border px-3 py-2 text-center transition-all duration-300", width, color, STATE[state])}>
      <Handles />
      <Planned node={node} />
      <div className="text-[13px] leading-snug font-semibold">{node.title}</div>
      {node.detail && <div className="text-[11px] leading-snug text-zinc-600">{node.detail}</div>}
    </div>
  );
}

function DecisionNode({ data }: NodeProps<Node<Data>>) {
  const { node, state } = data;
  const lit = state === "done" || state === "current";
  return (
    <div className={cn("relative flex h-[100px] w-[240px] items-center justify-center transition-all duration-300", state === "off" && "opacity-35", state === "current" && "scale-[1.04]")}>
      <Handles />
      <svg viewBox="0 0 240 100" className="absolute inset-0 h-full w-full" aria-hidden>
        <polygon points="120,2 238,50 120,98 2,50" className={cn("fill-white", lit ? "stroke-zinc-900" : "stroke-zinc-400")} strokeWidth={lit ? 3 : 1.5} />
      </svg>
      <Planned node={node} />
      <div className="relative px-12 text-center">
        <div className="text-[12px] leading-tight font-semibold">{node.title}</div>
        {node.detail && <div className="text-[10px] leading-tight text-zinc-500">{node.detail}</div>}
      </div>
    </div>
  );
}

const nodeTypes = { box: BoxNode, decision: DecisionNode };

function stateOf(id: string, path: string[], step: number, finished: boolean): State {
  const at = path.indexOf(id);
  if (at === -1) return finished ? "off" : "idle";
  if (at < step) return "done";
  return at === step ? "current" : "idle";
}

export function FlowWalkthrough({ initial }: { initial: string }) {
  const [scenarioId, setScenarioId] = useState(initial);
  const [step, setStep] = useState(0);
  const scenario = SCENARIOS.find((s) => s.id === scenarioId)!;
  const path = useMemo(() => walk(scenario), [scenario]);
  const last = path.nodes.length - 1;
  const finished = step >= last;

  useEffect(() => {
    if (finished) return;
    const t = setTimeout(() => setStep((s) => s + 1), STEP_MS);
    return () => clearTimeout(t);
  }, [step, finished]);

  const choose = (id: string) => {
    setScenarioId(id);
    setStep(0);
  };

  const nodes: Node<Data>[] = NODES.map((n) => ({
    id: n.id,
    type: n.kind === "decision" ? "decision" : "box",
    position: { x: n.x, y: n.y },
    data: { node: n, state: stateOf(n.id, path.nodes, step, finished) },
    draggable: false,
    selectable: false,
  }));

  const edges: Edge[] = EDGES.map((e) => {
    const walked = path.edges.indexOf(e.id);
    const lit = (walked !== -1 && walked < step) || (!!e.loop && finished && path.end === e.source);
    const color = lit ? (scenario.normal ? "#15803d" : "#b91c1c") : e.loop ? "#86efac" : "#a1a1aa";
    return {
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: `s-${e.sourceHandle ?? "bottom"}`,
      targetHandle: `t-${e.targetHandle ?? "top"}`,
      type: "smoothstep",
      label: e.when === undefined ? (e.loop ? "used next time" : undefined) : e.when ? "Yes" : "No",
      labelStyle: { fontSize: 11, fontWeight: 600, fill: lit ? color : "#52525b" },
      labelBgStyle: { fill: "#ffffff" },
      animated: lit,
      style: { stroke: color, strokeWidth: lit ? 3 : 1.5, strokeDasharray: e.loop && !lit ? "6 4" : undefined },
      markerEnd: { type: MarkerType.ArrowClosed, color },
      focusable: false,
    };
  });

  const end = NODES.find((n) => n.id === path.end)!;

  return (
    <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
      <div className="flex flex-col gap-4 lg:sticky lg:top-4 lg:self-start">
        {[true, false].map((normal) => (
          <Card key={String(normal)} className="gap-2 py-4">
            <CardHeader className="px-4">
              <CardTitle className="text-sm">{normal ? "Normal payments" : "Impersonation attempts"}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-1 px-2">
              {SCENARIOS.filter((s) => s.normal === normal).map((s) => (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => choose(s.id)}
                  className={cn(
                    "rounded-md px-2 py-1.5 text-left transition-colors hover:bg-muted",
                    s.id === scenarioId && (normal ? "bg-green-50 ring-1 ring-green-300" : "bg-red-50 ring-1 ring-red-300"),
                  )}
                >
                  <div className="text-sm font-medium">{s.title}</div>
                  <div className="text-xs text-muted-foreground">{s.summary}</div>
                </button>
              ))}
            </CardContent>
          </Card>
        ))}

        <Card className={cn("gap-2 py-4", finished && end.kind === "end" && TONE[end.tone])}>
          <CardHeader className="px-4">
            <CardDescription>Outcome</CardDescription>
            <CardTitle className="text-base">{finished ? end.title : "Following the rules…"}</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3 px-4">
            <p className="text-sm">{finished ? scenario.outcome : `Step ${step + 1} of ${last + 1}`}</p>
            <Button variant="outline" size="sm" className="self-start bg-white" onClick={() => setStep(0)}>
              <RotateCcw /> Replay
            </Button>
          </CardContent>
        </Card>

        <Card className="gap-2 py-4">
          <CardContent className="flex flex-col gap-1.5 px-4 text-xs">
            {(Object.keys(ROLE) as Role[]).map((r) => (
              <div key={r} className="flex items-center gap-2">
                <span className={cn("size-3 rounded-sm border", ROLE[r])} />
                {ROLE_NAME[r]}
              </div>
            ))}
            <div className="flex items-center gap-2">
              <span className="rounded-full border border-dashed border-zinc-400 px-1.5 text-[10px] leading-4 text-zinc-500">planned</span>
              Designed, not in the app yet
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="h-[1180px] overflow-hidden p-0">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.04 }}
          nodesConnectable={false}
          zoomOnScroll={false}
          preventScrolling={false}
          minZoom={0.4}
        >
          <Background gap={24} color="#e4e4e7" />
        </ReactFlow>
      </Card>
    </div>
  );
}
