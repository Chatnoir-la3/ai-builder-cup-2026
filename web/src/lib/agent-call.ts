// The verification call in the browser: the agent's reply arrives as one JSON event per line (agent call.py),
// its voice as 16-bit PCM at 24 kHz; the payee's voice goes up as 16-bit PCM at 16 kHz.

import type { CallOutcome } from "@/lib/payguard";

export type { CallOutcome };

export const AGENT = "Verification agent";
export const PLAYBACK_RATE = 24_000;
export const RECORD_RATE = 16_000;

export type CallEvent =
  | { type: "audio"; data: string }
  | { type: "said" | "heard"; text: string }
  | { type: "done"; outcome: CallOutcome }
  | { type: "error"; text: string };

export function splitEvents(buffer: string): { events: CallEvent[]; rest: string } {
  const lines = buffer.split("\n");
  const rest = lines.pop() ?? "";
  const events: CallEvent[] = [];
  for (const line of lines) {
    if (!line.trim()) continue;
    try {
      events.push(JSON.parse(line) as CallEvent);
    } catch {
      // a line that is not JSON carries nothing the call needs
    }
  }
  return { events, rest };
}

export function floatToPcm16(samples: Float32Array): Int16Array {
  const out = new Int16Array(samples.length);
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    out[i] = s < 0 ? Math.round(s * 32768) : Math.round(s * 32767);
  }
  return out;
}

// Microphones record at the device rate (often 48 kHz); the agent wants 16 kHz. Averages each window.
export function downsample(samples: Float32Array, fromRate: number, toRate = RECORD_RATE): Float32Array {
  if (fromRate === toRate) return samples;
  const ratio = fromRate / toRate;
  const out = new Float32Array(Math.floor(samples.length / ratio));
  for (let i = 0; i < out.length; i++) {
    const start = Math.floor(i * ratio);
    const end = Math.min(samples.length, Math.floor((i + 1) * ratio));
    let sum = 0;
    for (let j = start; j < end; j++) sum += samples[j];
    out[i] = end > start ? sum / (end - start) : 0;
  }
  return out;
}

export function pcm16ToFloat(pcm: Int16Array): Float32Array<ArrayBuffer> {
  const out = new Float32Array(pcm.length);
  for (let i = 0; i < pcm.length; i++) out[i] = pcm[i] / 32768;
  return out;
}

export function pcm16ToBase64(pcm: Int16Array): string {
  const bytes = new Uint8Array(pcm.buffer, pcm.byteOffset, pcm.byteLength);
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(binary);
}

export function base64ToPcm16(data: string): Int16Array {
  const binary = atob(data);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return new Int16Array(bytes.buffer, 0, bytes.length >> 1);
}

// Relays the agent's streamed reply to the browser, or turns a refusal into the usual { error } JSON.
export async function relayCall(res: Response, fallback: string): Promise<Response> {
  if (!res.ok || !res.body) {
    const data = (await res.json().catch(() => ({}))) as { detail?: string };
    const error =
      res.status === 429 ? "The demo has reached its hourly limit. Try again later." : (data.detail ?? fallback);
    return Response.json({ error }, { status: res.ok ? 502 : res.status });
  }
  return new Response(res.body, {
    headers: {
      "Content-Type": "application/x-ndjson",
      "Cache-Control": "no-cache, no-transform",
      "Content-Encoding": "identity",
    },
  });
}
