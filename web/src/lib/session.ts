import { cookies } from "next/headers";

// Who this browser acts as, and an id for the browser itself. The agent requires the second approval to
// come from a different browser session than the call. There is no sign-in: this shows separation, not identity.
export const SESSION_COOKIE = "pg_session";
export const ACTING_AS_COOKIE = "pg_acting_as";

const OPTIONS = {
  httpOnly: true,
  sameSite: "lax",
  secure: process.env.NODE_ENV === "production",
  path: "/",
  maxAge: 60 * 60 * 24 * 7,
} as const;

export async function readSession(): Promise<{ session: string | null; actingAs: string | null }> {
  const jar = await cookies();
  const actingAs = jar.get(ACTING_AS_COOKIE)?.value;
  return { session: jar.get(SESSION_COOKIE)?.value ?? null, actingAs: actingAs ? decodeURIComponent(actingAs) : null };
}

export async function setActingAs(name: string): Promise<void> {
  const jar = await cookies();
  if (!jar.get(SESSION_COOKIE)) jar.set(SESSION_COOKIE, crypto.randomUUID(), OPTIONS);
  jar.set(ACTING_AS_COOKIE, encodeURIComponent(name), OPTIONS);
}
