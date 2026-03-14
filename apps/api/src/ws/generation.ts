import { Hono } from "hono";
import { createBunWebSocket } from "hono/bun";

const { upgradeWebSocket, websocket } = createBunWebSocket();

export const wsRoutes = new Hono();

export { websocket };

const AGENT_SERVICE_URL =
	process.env.AGENT_SERVICE_URL || "http://localhost:8000";
const MOCK_API = process.env.MOCK_API === "true";

const MOCK_RESULT_URL =
	"https://placehold.co/1024x768/1a1a2e/eee?text=Generated+Design&font=noto-sans-jp";

const STATUS_MESSAGES: Record<string, string> = {
	queued: "キューに追加しました",
	decomposing: "クエリを分解中...",
	searching: "参考画像を検索中...",
	reranking: "参考画像をスコアリング中...",
	building_prompt: "生成プロンプトを構築中...",
	generating: "画像を生成中...",
	uploading: "画像をアップロード中...",
	completed: "完了",
	failed: "エラーが発生しました",
};

const MOCK_STEPS: { progress: number; status: string; message: string }[] = [
	{ progress: 0, status: "queued", message: "キューに追加しました" },
	{ progress: 25, status: "searching", message: "参考画像を検索中..." },
	{ progress: 50, status: "generating", message: "画像を生成中..." },
	{ progress: 75, status: "uploading", message: "仕上げ処理中..." },
	{ progress: 100, status: "completed", message: "完了" },
];

function streamDummyProgress(
	ws: { send: (data: string) => void },
	jobId: string,
) {
	let step = 0;
	const interval = setInterval(() => {
		const s = MOCK_STEPS[step];
		ws.send(
			JSON.stringify({
				type: "progress",
				job_id: jobId,
				progress: s.progress,
				status: s.status,
				message: s.message,
				...(s.progress === 100 ? { result_url: MOCK_RESULT_URL } : {}),
			}),
		);
		step++;
		if (step >= MOCK_STEPS.length) clearInterval(interval);
	}, 600);
}

async function streamRealProgress(
	ws: { send: (data: string) => void },
	jobId: string,
) {
	const pollInterval = 1500;
	const maxPolls = 200;
	let consecutiveErrors = 0;

	for (let i = 0; i < maxPolls; i++) {
		await new Promise((r) => setTimeout(r, pollInterval));

		try {
			const resp = await fetch(
				`${AGENT_SERVICE_URL}/api/v1/jobs/${jobId}`,
			);
			if (!resp.ok) {
				consecutiveErrors++;
				if (consecutiveErrors > 5) {
					ws.send(
						JSON.stringify({
							type: "progress",
							job_id: jobId,
							progress: 0,
							status: "failed",
							message: "Agent Service との接続が切断されました",
						}),
					);
					return;
				}
				continue;
			}

			consecutiveErrors = 0;
			const data = await resp.json();

			const status = data.status || "unknown";
			const progress = data.progress || 0;
			const message = STATUS_MESSAGES[status] || status;

			ws.send(
				JSON.stringify({
					type: "progress",
					job_id: jobId,
					progress,
					status,
					message,
					...(status === "completed" && data.image_url
						? { result_url: data.image_url }
						: {}),
					...(data.is_mock !== undefined
						? { is_mock: data.is_mock }
						: {}),
					...(data.provider ? { provider: data.provider } : {}),
				}),
			);

			if (status === "completed" || status === "failed") {
				return;
			}
		} catch {
			consecutiveErrors++;
			if (consecutiveErrors > 5) {
				ws.send(
					JSON.stringify({
						type: "progress",
						job_id: jobId,
						progress: 0,
						status: "failed",
						message: "Agent Service へのポーリングに失敗しました",
					}),
				);
				return;
			}
		}
	}

	ws.send(
		JSON.stringify({
			type: "progress",
			job_id: jobId,
			progress: 0,
			status: "failed",
			message: "タイムアウト: 生成に時間がかかりすぎています",
		}),
	);
}

wsRoutes.get(
	"/generation",
	upgradeWebSocket((c) => {
		return {
			onOpen(_event, ws) {
				console.log("WebSocket client connected");
				ws.send(
					JSON.stringify({
						type: "connected",
						message: "Connected to generation progress stream",
					}),
				);
			},

			onMessage(event, ws) {
				try {
					const data = JSON.parse(String(event.data));

					if (data.type === "subscribe" && data.job_id) {
						ws.send(
							JSON.stringify({
								type: "subscribed",
								job_id: data.job_id,
							}),
						);

						if (MOCK_API) {
							streamDummyProgress(ws, data.job_id);
						} else {
							streamRealProgress(ws, data.job_id);
						}
					}
				} catch {
					ws.send(
						JSON.stringify({
							type: "error",
							message: "Invalid JSON",
						}),
					);
				}
			},

			onClose() {
				console.log("WebSocket client disconnected");
			},
		};
	}),
);
