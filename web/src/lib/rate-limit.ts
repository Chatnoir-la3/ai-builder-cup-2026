// Fixed-window limit per client IP, per instance. Enough to keep the public demo from running up model calls.
const windows = new Map<string, { start: number; count: number }>();

// Cloud Run appends the address it saw to X-Forwarded-For; anything before it is whatever the client sent.
export function clientIp(request: Request): string {
  return request.headers.get("x-forwarded-for")?.split(",").at(-1)?.trim() || "local";
}

export function allow(key: string, limit: number, windowMs: number): boolean {
  const now = Date.now();
  const w = windows.get(key);
  if (!w || now - w.start >= windowMs) {
    windows.set(key, { start: now, count: 1 });
    return true;
  }
  w.count += 1;
  return w.count <= limit;
}
