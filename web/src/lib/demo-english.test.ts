import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { ABOUT, PAYEE_EN, START_WITH, TRANSLATION } from "@/lib/demo-english";

const DATA = join(__dirname, "../../../agent/app/payguard/data");
const ORIGINALS = join(DATA, "originals");
const files = readdirSync(ORIGINALS).filter((f) => statSync(join(ORIGINALS, f)).isFile());
const scenarios = JSON.parse(readFileSync(join(DATA, "scenarios.json"), "utf-8")) as {
  payment: { id: string; payee_name: string };
}[];

describe("demo English", () => {
  it("covers every original, payment and payee in the demo data", () => {
    expect(Object.keys(TRANSLATION).sort()).toEqual([...files].sort());
    expect(Object.keys(ABOUT).sort()).toEqual(scenarios.map((s) => s.payment.id).sort());
    for (const s of scenarios) expect(PAYEE_EN[s.payment.payee_name]).toBeTruthy();
    expect(ABOUT[START_WITH]).toBeTruthy();
  });

  // Addresses, links, account numbers and amounts must read the same in both languages.
  it.each(files.filter((f) => f.endsWith(".txt")))("keeps the addresses and numbers of %s", (name) => {
    const original = readFileSync(join(ORIGINALS, name), "utf-8");
    const facts = original.match(/[\w.+-]+@[\w.-]+|https?:\/\/[^\s<>]+|\d[\d,]{4,}/g) ?? [];
    expect(facts.length).toBeGreaterThan(0);
    for (const fact of facts) expect(TRANSLATION[name]).toContain(fact);
  });
});
