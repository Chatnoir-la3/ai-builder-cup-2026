"use client";

import { Mic, PhoneCall, PhoneOff, Send, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  PLAYBACK_RATE,
  base64ToPcm16,
  downsample,
  floatToPcm16,
  isSilent,
  pcm16ToBase64,
  pcm16ToFloat,
  splitEvents,
  type CallEvent,
  type CallOutcome,
} from "@/lib/agent-call";
import { CALL_ROLE } from "@/lib/demo-english";
import { cn } from "@/lib/utils";

type Phase = "idle" | "dialing" | "connected" | "recording" | "waiting" | "done";
type Line = { speaker: "agent" | "payee"; text: string };

const MAX_RECORD_MS = 29_000;
// Copies microphone frames to the page; the page downsamples and encodes them when the payee stops talking.
const TAP = `class Tap extends AudioWorkletProcessor {
  process(inputs) { const ch = inputs[0] && inputs[0][0]; if (ch) this.port.postMessage(ch.slice(0)); return true; }
}
registerProcessor("tap", Tap);`;

const OUTCOME_TEXT: Record<CallOutcome, string> = {
  confirmed: "What they stated matches the transfer. Read the call, then approve.",
  mismatch: "They stated something different from the transfer. The payment is on hold.",
  denied: "They made no such request. The payment is on hold.",
  incomplete: "Nothing was confirmed. Call the number yourself.",
};

type Recorder = { ctx: AudioContext; stream: MediaStream; frames: Float32Array[]; timer: number };

export function VerificationCall({
  paymentId,
  contactName,
  onFinished,
}: {
  paymentId: string;
  contactName: string;
  onFinished: () => void;
}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [lines, setLines] = useState<Line[]>([]);
  const [outcome, setOutcome] = useState<CallOutcome | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [typed, setTyped] = useState("");
  const [speaking, setSpeaking] = useState(false);
  const player = useRef<{ ctx: AudioContext; next: number } | null>(null);
  const recorder = useRef<Recorder | null>(null);
  const freshTurn = useRef(true);
  const role = CALL_ROLE[paymentId];

  useEffect(
    () => () => {
      void player.current?.ctx.close();
      stopTracks(recorder.current);
    },
    [],
  );

  function play(data: string) {
    if (!player.current) {
      const ctx = new AudioContext({ sampleRate: PLAYBACK_RATE });
      player.current = { ctx, next: ctx.currentTime };
    }
    const p = player.current;
    const samples = pcm16ToFloat(base64ToPcm16(data));
    const buffer = p.ctx.createBuffer(1, samples.length, PLAYBACK_RATE);
    buffer.copyToChannel(samples, 0);
    const source = p.ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(p.ctx.destination);
    const at = Math.max(p.next, p.ctx.currentTime);
    source.start(at);
    p.next = at + buffer.duration;
    setSpeaking(true);
    source.onended = () => {
      if (player.current && player.current.ctx.currentTime >= player.current.next - 0.05) setSpeaking(false);
    };
  }

  function stopPlayback() {
    void player.current?.ctx.close();
    player.current = null;
    setSpeaking(false);
  }

  function add(speaker: Line["speaker"], text: string) {
    setLines((prev) => {
      const last = prev.at(-1);
      if (last && last.speaker === speaker && !freshTurn.current) {
        return [...prev.slice(0, -1), { speaker, text: last.text + text }];
      }
      freshTurn.current = false;
      return [...prev, { speaker, text: text.trimStart() }];
    });
  }

  function handle(event: CallEvent) {
    if (event.type === "audio") play(event.data);
    else if (event.type === "said") add("agent", event.text);
    else if (event.type === "heard") add("payee", event.text);
    else if (event.type === "error") setError(event.text);
    else if (event.type === "done") {
      setOutcome(event.outcome);
      setPhase("done");
      onFinished();
    }
  }

  async function follow(request: Promise<Response>) {
    freshTurn.current = true;
    try {
      const res = await request;
      if (!res.ok || !res.body) {
        const data = (await res.json().catch(() => ({}))) as { error?: string };
        throw new Error(data.error ?? "The call dropped. Call the number yourself.");
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let rest = "";
      let finished = false;
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        const split = splitEvents(rest + decoder.decode(value, { stream: true }));
        rest = split.rest;
        for (const event of split.events) {
          handle(event);
          if (event.type === "done") finished = true;
        }
      }
      if (!finished) setPhase("connected");
    } catch (e) {
      setError(e instanceof Error ? e.message : "The call dropped. Call the number yourself.");
      setPhase((p) => (p === "dialing" ? "idle" : "connected"));
    }
  }

  function startCall() {
    setError(null);
    setLines([]);
    setOutcome(null);
    setPhase("dialing");
    player.current = { ctx: new AudioContext({ sampleRate: PLAYBACK_RATE }), next: 0 }; // created on the click
    void follow(fetch(`/api/payments/${paymentId}/agent-call`, { method: "POST" }));
  }

  function say(body: { audio: string } | { text: string }) {
    setError(null);
    setPhase("waiting");
    void follow(
      fetch(`/api/payments/${paymentId}/agent-call/say`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    );
  }

  function sendTyped(text: string) {
    const t = text.trim();
    if (!t) return;
    setTyped("");
    freshTurn.current = true;
    setLines((prev) => [...prev, { speaker: "payee", text: t }]);
    say({ text: t });
  }

  async function startTalking() {
    setError(null);
    stopPlayback(); // talking over the agent stops it
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
      const ctx = new AudioContext();
      await ctx.audioWorklet.addModule(URL.createObjectURL(new Blob([TAP], { type: "text/javascript" })));
      const node = new AudioWorkletNode(ctx, "tap");
      const frames: Float32Array[] = [];
      node.port.onmessage = (e: MessageEvent<Float32Array>) => frames.push(e.data);
      ctx.createMediaStreamSource(stream).connect(node);
      const timer = window.setTimeout(() => void stopTalking(), MAX_RECORD_MS);
      recorder.current = { ctx, stream, frames, timer };
      setPhase("recording");
    } catch {
      setError("The microphone is not available. Type what the payee says instead.");
    }
  }

  async function stopTalking() {
    const r = recorder.current;
    if (!r) return;
    recorder.current = null;
    window.clearTimeout(r.timer);
    stopTracks(r);
    const rate = r.ctx.sampleRate;
    await r.ctx.close();
    const total = r.frames.reduce((n, f) => n + f.length, 0);
    const all = new Float32Array(total);
    let offset = 0;
    for (const f of r.frames) {
      all.set(f, offset);
      offset += f.length;
    }
    if (total < rate / 4) {
      setPhase("connected");
      setError("That was too short. Hold the button while you speak.");
      return;
    }
    if (isSilent(all, rate)) {
      setPhase("connected");
      setError("Nothing was heard. Check your microphone, then press Talk and speak.");
      return;
    }
    say({ audio: pcm16ToBase64(floatToPcm16(downsample(all, rate))) });
  }

  async function hangUp() {
    stopPlayback();
    stopTracks(recorder.current);
    recorder.current = null;
    const res = await fetch(`/api/payments/${paymentId}/agent-call/hang-up`, { method: "POST" }).catch(() => null);
    const data = res?.ok ? ((await res.json()) as CallEvent) : null;
    setOutcome(data?.type === "done" ? data.outcome : "incomplete");
    setPhase("done");
    onFinished();
  }

  const inCall = phase === "connected" || phase === "recording" || phase === "waiting";

  return (
    <div className="flex flex-col gap-3">
      {phase === "idle" && (
        <>
          <Button onClick={startCall} className="w-full">
            <PhoneCall />
            Let the agent call {contactName}
          </Button>
          <p className="text-xs text-muted-foreground">
            Gemini Live calls the number above. A supplier is asked for the bank and the last four digits of the
            account; someone named in a request, whether they asked for it and how much. The agent is never told
            the account or the amount, so it cannot lead them; code compares what they state with the transfer.
          </p>
        </>
      )}

      {phase === "dialing" && (
        <div className="flex items-center gap-2 text-sm">
          <PhoneCall className="size-4 animate-pulse" />
          Calling {contactName}…
        </div>
      )}

      {role && phase !== "idle" && phase !== "done" && (
        <div className="rounded-md border border-dashed bg-background p-3 text-xs">
          <div className="font-medium">In this demo, you answer as {role.role}.</div>
          <ul className="mt-1.5 flex flex-col gap-1.5">
            {role.lines.map((l) => (
              <li key={l.label}>
                <span className="text-muted-foreground">{l.label}: </span>
                <button
                  type="button"
                  className="text-left underline decoration-dotted underline-offset-2 disabled:no-underline disabled:opacity-60"
                  disabled={phase !== "connected"}
                  onClick={() => sendTyped(l.say)}
                >
                  “{l.say}”
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {lines.length > 0 && (
        <ol className="flex max-h-72 flex-col gap-2 overflow-y-auto rounded-md border bg-background p-3 text-sm" aria-live="polite">
          {lines.map((l, i) => (
            <li key={i} className={cn("flex flex-col", l.speaker === "payee" && "items-end")}>
              <span className="text-xs text-muted-foreground">{l.speaker === "agent" ? "Agent" : contactName}</span>
              <span
                className={cn(
                  "max-w-[90%] rounded-md px-2.5 py-1.5",
                  l.speaker === "agent" ? "bg-muted" : "bg-primary text-primary-foreground",
                )}
              >
                {l.text}
              </span>
            </li>
          ))}
        </ol>
      )}

      {inCall && (
        <>
          <div className="flex items-center gap-2">
            {phase === "recording" ? (
              <Button className="flex-1" variant="destructive" onClick={() => void stopTalking()}>
                <Square />
                Done talking
              </Button>
            ) : (
              <Button className="flex-1" disabled={phase === "waiting"} onClick={() => void startTalking()}>
                <Mic />
                {phase === "waiting" ? "Agent is replying…" : speaking ? "Talk (interrupts the agent)" : "Talk"}
              </Button>
            )}
            <Button variant="outline" className="bg-background" onClick={() => void hangUp()} aria-label="Hang up">
              <PhoneOff />
            </Button>
          </div>
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              sendTyped(typed);
            }}
          >
            <Input
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              placeholder="Or type what you say"
              maxLength={500}
              disabled={phase !== "connected"}
              className="bg-background"
            />
            <Button type="submit" size="icon" variant="outline" className="bg-background" disabled={phase !== "connected" || !typed.trim()} aria-label="Send">
              <Send />
            </Button>
          </form>
        </>
      )}

      {phase === "done" && outcome && (
        <p
          className={cn(
            "rounded-md border p-3 text-sm font-medium",
            outcome === "confirmed" ? "border-emerald-300 bg-emerald-50 text-emerald-900" : "border-red-300 bg-red-50 text-red-900",
            outcome === "incomplete" && "border-amber-300 bg-amber-50 text-amber-900",
          )}
        >
          {OUTCOME_TEXT[outcome]}
        </p>
      )}

      {error && <p className="text-sm text-red-800">{error}</p>}
    </div>
  );
}

function stopTracks(r: Recorder | null) {
  r?.stream.getTracks().forEach((t) => t.stop());
}
