import { agentFetch } from "@/lib/agent";
import { allow, clientIp } from "@/lib/rate-limit";
import { readSession } from "@/lib/session";

export async function POST(request: Request, ctx: RouteContext<"/api/payments/[id]/call">) {
  const { id } = await ctx.params;
  if (!allow(`call:${clientIp(request)}`, 60, 10 * 60_000)) {
    return Response.json({ error: "Too many requests. Try again in a few minutes." }, { status: 429 });
  }
  const body = (await request.json().catch(() => null)) as { confirmed?: unknown } | null;
  if (typeof body?.confirmed !== "boolean") {
    return Response.json({ error: "invalid request" }, { status: 400 });
  }
  // The caller is whoever this browser acts as, never a name sent in the request.
  const { session, actingAs } = await readSession();
  if (!session || !actingAs) return Response.json({ error: "Choose who you are first." }, { status: 409 });
  try {
    const res = await agentFetch(`/demo/payments/${encodeURIComponent(id)}/call`, {
      method: "POST",
      body: JSON.stringify({ by: actingAs, confirmed: body.confirmed, session }),
    });
    const data = (await res.json().catch(() => ({}))) as { detail?: string };
    if (!res.ok) return Response.json({ error: data.detail ?? "The call was not saved." }, { status: res.status });
    return Response.json(data);
  } catch {
    return Response.json({ error: "The call was not saved." }, { status: 502 });
  }
}
