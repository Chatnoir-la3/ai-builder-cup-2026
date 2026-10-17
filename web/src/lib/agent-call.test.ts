import { describe, expect, it } from "vitest";

import { base64ToPcm16, downsample, floatToPcm16, isSilent, pcm16ToBase64, pcm16ToFloat, splitEvents } from "@/lib/agent-call";

describe("splitEvents", () => {
  it("returns whole lines as events and keeps a partial line for the next chunk", () => {
    const first = splitEvents('{"type":"said","text":"Hel"}\n{"type":"au');
    expect(first.events).toEqual([{ type: "said", text: "Hel" }]);
    const second = splitEvents(first.rest + 'dio","data":"AAA="}\n');
    expect(second.events).toEqual([{ type: "audio", data: "AAA=" }]);
    expect(second.rest).toBe("");
  });

  it("skips blank and broken lines", () => {
    expect(splitEvents('\n{oops}\n{"type":"done","outcome":"confirmed"}\n').events).toEqual([
      { type: "done", outcome: "confirmed" },
    ]);
  });
});

describe("pcm", () => {
  it("clamps float samples into 16-bit range", () => {
    expect(Array.from(floatToPcm16(new Float32Array([0, 1, -1, 2, -2])))).toEqual([0, 32767, -32768, 32767, -32768]);
  });

  it("round-trips through base64", () => {
    const pcm = new Int16Array([0, 1, -1, 32767, -32768]);
    expect(Array.from(base64ToPcm16(pcm16ToBase64(pcm)))).toEqual(Array.from(pcm));
  });

  it("downsamples 48 kHz to 16 kHz by averaging", () => {
    const out = downsample(new Float32Array([0.3, 0.6, 0.9, -0.3, -0.6, -0.9]), 48_000);
    expect(out.length).toBe(2);
    expect(out[0]).toBeCloseTo(0.6);
    expect(out[1]).toBeCloseTo(-0.6);
    expect(downsample(new Float32Array([1, 2]), 16_000)).toEqual(new Float32Array([1, 2]));
  });

  it("treats a turn with no window above the floor as silent", () => {
    const rate = 16_000;
    const quiet = new Float32Array(rate).map((_, i) => 0.003 * Math.sin(i));
    expect(isSilent(quiet, rate)).toBe(true);
    const spoken = quiet.slice();
    for (let i = 8_000; i < 8_800; i++) spoken[i] = 0.2 * Math.sin(i / 3);
    expect(isSilent(spoken, rate)).toBe(false);
  });

  it("converts 16-bit samples to floats for playback", () => {
    expect(Array.from(pcm16ToFloat(new Int16Array([0, -32768])))).toEqual([0, -1]);
  });
});
