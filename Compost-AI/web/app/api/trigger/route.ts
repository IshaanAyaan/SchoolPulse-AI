import { NextResponse } from "next/server";
import { Redis } from "@upstash/redis";

export const dynamic = "force-dynamic";

const redis = new Redis({
  url: process.env.UPSTASH_REDIS_REST_URL!,
  token: process.env.UPSTASH_REDIS_REST_TOKEN!,
});

const KEY = "compost:trigger";

export async function POST() {
  await redis.set(KEY, "1", { ex: 30 }); // expires after 30s so stale triggers don't pile up
  return NextResponse.json({ ok: true });
}

export async function GET() {
  // Atomic get-and-delete. @upstash/redis auto-deserializes, so the stored "1"
  // comes back as the number 1 — check presence (non-null) rather than value.
  const fired = await redis.getdel(KEY);
  return NextResponse.json({ triggered: fired != null });
}
