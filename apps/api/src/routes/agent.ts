import { Hono } from "hono";
import { z } from "zod";
import { zValidator } from "@hono/zod-validator";

export const agentRoutes = new Hono();

const generateSchema = z.object({
	prompt: z.string().min(1),
	style_reference_ids: z.array(z.string()).optional(),
	layout_reference_ids: z.array(z.string()).optional(),
	brand: z.string().optional(),
	resolution: z
		.object({
			width: z.number().int().positive(),
			height: z.number().int().positive(),
		})
		.optional(),
	reference_mode: z.enum(["style_only", "layout_only", "hybrid"]).default("hybrid"),
});

const searchSchema = z.object({
	query: z.string().min(1),
	category: z.string().optional(),
	style_tags: z.string().optional(),
	limit: z.coerce.number().int().min(1).max(100).default(20),
});

const AGENT_SERVICE_URL = process.env.AGENT_SERVICE_URL || "http://localhost:8000";
const MOCK_API = process.env.MOCK_API === "true";

function mockGenerateResponse(body: z.infer<typeof generateSchema>) {
	return {
		job_id: `mock-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`,
		status: "queued",
		message: `Generation job queued (mock): ${body.prompt.slice(0, 80)}...`,
	};
}

function mockSearchResponse(params: { query: string }) {
	return {
		results: [
			{
				id: "mock-asset-1",
				score: 0.92,
				category: "banner",
				style_tags: ["minimal", "gradient"],
				caption: "ミニマルなグラデーションバナー、中央配置のタイポグラフィ",
				thumbnail_url: "https://placehold.co/400x300/1a1a2e/eee?text=Reference+1",
			},
			{
				id: "mock-asset-2",
				score: 0.88,
				category: "ui",
				style_tags: ["neon", "dark"],
				caption: "ネオンアクセントのダークUIモックアップ",
				thumbnail_url: "https://placehold.co/400x300/16213e/0f3460?text=Reference+2",
			},
		],
		total: 2,
		query: params.query,
	};
}

agentRoutes.post("/generate", zValidator("json", generateSchema), async (c) => {
	const body = c.req.valid("json");

	if (MOCK_API) {
		return c.json(mockGenerateResponse(body));
	}

	try {
		const response = await fetch(`${AGENT_SERVICE_URL}/api/v1/generate`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify(body),
		});

		if (!response.ok) {
			return c.json({ error: "Agent service error", status: response.status }, 502);
		}

		const result = await response.json();
		return c.json(result);
	} catch {
		return c.json(mockGenerateResponse(body));
	}
});

agentRoutes.get("/search", zValidator("query", searchSchema), async (c) => {
	const params = c.req.valid("query");

	if (MOCK_API) {
		return c.json(mockSearchResponse(params));
	}

	try {
		const url = new URL(`${AGENT_SERVICE_URL}/api/v1/search`);
		url.searchParams.set("query", params.query);
		if (params.category) url.searchParams.set("category", params.category);
		if (params.style_tags) url.searchParams.set("style_tags", params.style_tags);
		url.searchParams.set("limit", String(params.limit));

		const response = await fetch(url.toString());

		if (!response.ok) {
			return c.json({ error: "Agent service error", status: response.status }, 502);
		}

		const result = await response.json();
		return c.json(result);
	} catch {
		return c.json(mockSearchResponse(params));
	}
});
