import { Hono } from "hono";

const COLLECTOR_SERVICE_URL =
	process.env.COLLECTOR_SERVICE_URL || "http://localhost:8400";

export const collectorRoutes = new Hono();

const proxy = async (
	method: string,
	path: string,
	body?: BodyInit | null,
	headers?: Headers,
) => {
	const res = await fetch(`${COLLECTOR_SERVICE_URL}${path}`, {
		method,
		headers,
		body,
	});
	const data = await res.json().catch(() => ({}));
	return { data, status: res.status };
};

collectorRoutes.post("/collector/jobs", async (c) => {
	try {
		const json = await c.req.json();
		const { data, status } = await proxy(
			"POST",
			"/api/v1/jobs",
			JSON.stringify(json),
			new Headers({ "Content-Type": "application/json" }),
		);
		return c.json(data, status as 200);
	} catch {
		return c.json({ error: "Collector service unavailable" }, 503);
	}
});

collectorRoutes.get("/collector/jobs", async (c) => {
	try {
		const { data, status } = await proxy("GET", "/api/v1/jobs");
		return c.json(data, status as 200);
	} catch {
		return c.json({ error: "Collector service unavailable" }, 503);
	}
});

collectorRoutes.get("/collector/jobs/:id", async (c) => {
	const id = c.req.param("id");
	try {
		const { data, status } = await proxy("GET", `/api/v1/jobs/${id}`);
		return c.json(data, status as 200);
	} catch {
		return c.json({ error: "Collector service unavailable" }, 503);
	}
});

collectorRoutes.get("/collector/jobs/:id/images", async (c) => {
	const id = c.req.param("id");
	try {
		const { data, status } = await proxy(
			"GET",
			`/api/v1/jobs/${id}/images`,
		);
		return c.json(data, status as 200);
	} catch {
		return c.json({ error: "Collector service unavailable" }, 503);
	}
});

collectorRoutes.get("/collector/local/files", async (c) => {
	const source = c.req.query("source");
	try {
		const qs = source ? `?source=${encodeURIComponent(source)}` : "";
		const { data, status } = await proxy("GET", `/api/v1/local/files${qs}`);
		return c.json(data, status as 200);
	} catch {
		return c.json({ error: "Collector service unavailable" }, 503);
	}
});

collectorRoutes.post("/collector/local/ingest", async (c) => {
	try {
		const json = await c.req.json();
		const { data, status } = await proxy(
			"POST",
			"/api/v1/local/ingest",
			JSON.stringify(json),
			new Headers({ "Content-Type": "application/json" }),
		);
		return c.json(data, status as 200);
	} catch {
		return c.json({ error: "Collector service unavailable" }, 503);
	}
});

collectorRoutes.get("/collector/local/ingest/:id", async (c) => {
	const id = c.req.param("id");
	try {
		const { data, status } = await proxy("GET", `/api/v1/local/ingest/${id}`);
		return c.json(data, status as 200);
	} catch {
		return c.json({ error: "Collector service unavailable" }, 503);
	}
});
