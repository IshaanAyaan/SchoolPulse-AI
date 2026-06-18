import { withSupabase } from "npm:@supabase/server";

type JsonRecord = Record<string, unknown>;

function json(data: unknown, status = 200): Response {
  return Response.json(data, { status });
}

function asRecords(value: unknown): JsonRecord[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is JsonRecord => Boolean(item) && typeof item === "object" && !Array.isArray(item));
}

export default {
  fetch: withSupabase({ auth: "secret" }, async (req, ctx) => {
    if (req.method === "GET") {
      const { data, error } = await ctx.supabaseAdmin
        .from("schoolprint_agent_runs")
        .select("id, created_at, prompt, answer, module, used_llm, action_cards, citations")
        .order("created_at", { ascending: false })
        .limit(20);

      if (error) return json({ error: error.message }, 500);
      return json({ runs: data ?? [] });
    }

    if (req.method !== "POST") {
      return json({ error: "Use GET or POST." }, 405);
    }

    const body = await req.json().catch(() => null) as JsonRecord | null;
    if (!body || typeof body.kind !== "string") {
      return json({ error: "Body must include a kind field." }, 400);
    }

    if (body.kind === "agent_run") {
      const { data, error } = await ctx.supabaseAdmin
        .from("schoolprint_agent_runs")
        .insert({
          prompt: String(body.prompt ?? ""),
          answer: String(body.answer ?? ""),
          module: body.module ? String(body.module) : null,
          used_llm: Boolean(body.used_llm),
          action_cards: body.action_cards ?? [],
          citations: body.citations ?? [],
          metadata: body.metadata ?? {},
        })
        .select()
        .single();

      if (error) return json({ error: error.message }, 500);
      return json({ inserted: data });
    }

    if (body.kind === "operations_logs") {
      const records = asRecords(body.records);
      if (!records.length) return json({ error: "records must be a non-empty array." }, 400);

      const rows = records.map((record) => ({
        event_time: record.event_time ?? record.timestamp ?? null,
        module: String(record.module ?? "other"),
        source: String(record.source ?? "sync"),
        payload: record.payload ?? record,
        metadata: record.metadata ?? {},
      }));

      const { data, error } = await ctx.supabaseAdmin
        .from("schoolprint_operations_logs")
        .insert(rows)
        .select("id");

      if (error) return json({ error: error.message }, 500);
      return json({ inserted_count: data?.length ?? 0 });
    }

    if (body.kind === "source_documents") {
      const records = asRecords(body.records);
      if (!records.length) return json({ error: "records must be a non-empty array." }, 400);

      const rows = records.map((record) => ({
        source_type: String(record.source_type ?? "drive"),
        title: String(record.title ?? "Untitled school source"),
        url: String(record.url ?? ""),
        content: record.content ? String(record.content) : null,
        metadata: record.metadata ?? {},
      }));

      const { data, error } = await ctx.supabaseAdmin
        .from("schoolprint_source_documents")
        .upsert(rows, { onConflict: "source_type,title,url" })
        .select("id");

      if (error) return json({ error: error.message }, 500);
      return json({ upserted_count: data?.length ?? 0 });
    }

    return json({ error: `Unknown sync kind: ${body.kind}` }, 400);
  }),
};

