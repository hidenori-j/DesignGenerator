import { Hono } from "hono";

const INGEST_SERVICE_URL = process.env.INGEST_SERVICE_URL || "http://localhost:8200";

export const ingestRoutes = new Hono();

ingestRoutes.post("/ingest", async (c) => {
	try {
		const body = await c.req.raw.clone().arrayBuffer();
		const headers = new Headers(c.req.raw.headers);
		headers.delete("host");
		const res = await fetch(`${INGEST_SERVICE_URL}/api/v1/ingest`, {
			method: "POST",
			headers,
			body,
		});
		const data = await res.json().catch(() => ({}));
		return c.json(data, res.status as 200);
	} catch {
		return c.json({ error: "Ingest service unavailable" }, 503);
	}
});

ingestRoutes.post("/ingest/batch", async (c) => {
	try {
		const body = await c.req.raw.clone().arrayBuffer();
		const headers = new Headers(c.req.raw.headers);
		headers.delete("host");
		const res = await fetch(`${INGEST_SERVICE_URL}/api/v1/ingest/batch`, {
			method: "POST",
			headers,
			body,
		});
		const data = await res.json().catch(() => ({}));
		return c.json(data, res.status as 200);
	} catch {
		return c.json({ error: "Ingest service unavailable" }, 503);
	}
});
