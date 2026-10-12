import { allow, clientIp } from "@/lib/rate-limit";
import { setActingAs } from "@/lib/session";

export async function POST(request: Request) {
  if (!allow(`session:${clientIp(request)}`, 60, 10 * 60_000)) {
    return Response.json({ error: "Too many requests. Try again in a few minutes." }, { status: 429 });
  }
  const body = (await request.json().catch(() => null)) as { actingAs?: unknown } | null;
  const name = body?.actingAs;
  if (typeof name !== "string" || name.length === 0 || name.length > 64) {
    return Response.json({ error: "invalid request" }, { status: 400 });
  }
  await setActingAs(name);
  return Response.json({ actingAs: name });
}
