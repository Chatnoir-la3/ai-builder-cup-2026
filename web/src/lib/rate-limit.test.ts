import { describe, expect, it } from "vitest";

import { allow, clientIp } from "@/lib/rate-limit";

const from = (forwardedFor?: string) =>
  new Request("https://demo.example/api/session", { headers: forwardedFor ? { "x-forwarded-for": forwardedFor } : {} });

describe("clientIp", () => {
  it("takes the address the platform appended, not one the client sent", () => {
    expect(clientIp(from("203.0.113.7, 198.51.100.4"))).toBe("198.51.100.4");
    expect(clientIp(from("198.51.100.4"))).toBe("198.51.100.4");
  });

  it("falls back when the header is missing", () => {
    expect(clientIp(from())).toBe("local");
  });
});

describe("allow", () => {
  it("a forged header does not open a new window", () => {
    const key = (forged: string) => `t:${clientIp(from(`${forged}, 198.51.100.9`))}`;
    expect(allow(key("203.0.113.1"), 2, 60_000)).toBe(true);
    expect(allow(key("203.0.113.2"), 2, 60_000)).toBe(true);
    expect(allow(key("203.0.113.3"), 2, 60_000)).toBe(false);
  });
});
