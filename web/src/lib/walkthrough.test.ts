import { describe, expect, it } from "vitest";

import { EDGES, NODES, SCENARIOS, type Scenario, walk } from "@/lib/walkthrough";

const byId = (id: string) => SCENARIOS.find((s) => s.id === id)!;

describe("walk", () => {
  it.each([
    ["routine", "quiet"],
    ["phishing-link", "blocked-list"],
    ["lookalike-account-change", "held"],
    ["ceo-line-new-payee", "held"],
    ["fake-supplier", "blocked-no-number"],
    ["genuine-account-change", "recorded"],
    ["new-supplier", "recorded"],
  ])("%s ends at %s", (id, end) => {
    expect(walk(byId(id)).end).toBe(end);
  });

  it("follows edges that exist, in order", () => {
    for (const s of SCENARIOS) {
      const { nodes, edges } = walk(s);
      expect(edges).toHaveLength(nodes.length - 1);
      edges.forEach((id, i) => {
        const e = EDGES.find((x) => x.id === id)!;
        expect([e.source, e.target]).toEqual([nodes[i], nodes[i + 1]]);
      });
    }
  });

  it("shows nothing and calls no one for a routine payment", () => {
    const { nodes } = walk(byId("routine"));
    expect(nodes).not.toContain("explain");
    expect(nodes).not.toContain("call");
  });

  it("never sends money without a call and a second approval", () => {
    for (const s of SCENARIOS) {
      const { nodes } = walk(s);
      if (!nodes.includes("send")) continue;
      expect(nodes.indexOf("call")).toBeGreaterThan(-1);
      expect(nodes.indexOf("second")).toBeLessThan(nodes.indexOf("send"));
    }
  });

  it("fails loudly when a decision has no answer", () => {
    const broken: Scenario = { ...byId("routine"), answers: {} };
    expect(() => walk(broken)).toThrow(/differs|external/);
  });

  it("does not carry answers for decisions it never reaches", () => {
    for (const s of SCENARIOS) {
      const { nodes } = walk(s);
      expect(Object.keys(s.answers).filter((d) => !nodes.includes(d))).toEqual([]);
    }
  });
});

describe("graph", () => {
  it("gives every decision one yes and one no", () => {
    for (const n of NODES.filter((x) => x.kind === "decision")) {
      const out = EDGES.filter((e) => e.source === n.id && !e.loop);
      expect(out.map((e) => e.when).sort()).toEqual([false, true]);
    }
  });

  it("reaches every outcome with at least one scenario", () => {
    const ends = new Set(SCENARIOS.map((s) => walk(s).end));
    for (const n of NODES.filter((x) => x.kind === "end")) expect(ends).toContain(n.id);
  });
});
