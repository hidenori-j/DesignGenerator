import { Hono } from "hono";
import { cors } from "hono/cors";
import { logger } from "hono/logger";
import { agentRoutes } from "./routes/agent";
import { healthRoutes } from "./routes/health";
import { collectorRoutes } from "./routes/collector";
import { ingestRoutes } from "./routes/ingest";
import { wsRoutes, websocket } from "./ws/generation";

const app = new Hono();

app.use("*", logger());
app.use(
	"*",
	cors({
		origin: ["http://localhost:3000"],
		allowMethods: ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
		allowHeaders: ["Content-Type", "Authorization"],
	}),
);

app.route("/", healthRoutes);
app.route("/api/v1", agentRoutes);
app.route("/api/v1", ingestRoutes);
app.route("/api/v1", collectorRoutes);
app.route("/ws", wsRoutes);

const port = Number(process.env.API_PORT) || 4000;

export default {
	port,
	fetch: app.fetch,
	websocket,
};

console.log(`API Gateway running on http://localhost:${port}`);
