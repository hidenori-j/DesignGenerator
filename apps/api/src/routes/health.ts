import { Hono } from "hono";

export const healthRoutes = new Hono();

healthRoutes.get("/health", (c) => {
	return c.json({
		status: "ok",
		service: "api-gateway",
		timestamp: new Date().toISOString(),
	});
});
