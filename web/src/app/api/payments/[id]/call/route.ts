import { agentFetch } from "@/lib/agent";
import { allow, clientIp } from "@/lib/rate-limit";

export async function POST(request: Request, ctx: RouteContext<"/api/payments/[id]/call">) {
  const { id } = await ctx.params;
  if (!allow(`call:${clientIp(request)}`, 60, 10 * 60_000)) {
    return Response.json({ error: "Too many requests. Try again in a few minutes." }, { status: 429 });
  }
  const body = (await request.json().catch(() => null)) as { by?: unknown; confirmed?: unknown } | null;
  if (typeof body?.by !== "string" || typeof body.confirmed !== "boolean") {
    return Response.json({ error: "invalid request" }, { status: 400 });
  }
  try {
    const res = await agentFetch(`/demo/payments/${encodeURIComponent(id)}/call`, {
      method: "POST",
      body: JSON.stringify({ by: body.by, confirmed: body.confirmed }),
    });
    const data = (await res.json().catch(() => ({}))) as { detail?: string };
    if (!res.ok) return Response.json({ error: data.detail ?? "The call was not saved." }, { status: res.status });
    return Response.json(data);
  } catch {
    return Response.json({ error: "The call was not saved." }, { status: 502 });
  }
}
