"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { generateDesign, getWebSocketUrl } from "@/lib/api";

type Status =
	| "idle"
	| "queued"
	| "decomposing"
	| "searching"
	| "reranking"
	| "building_prompt"
	| "generating"
	| "uploading"
	| "completed"
	| "failed";

interface GenerationResult {
	url: string;
	isMock: boolean;
	provider?: string;
}

export default function GeneratorPage() {
	const [prompt, setPrompt] = useState("");
	const [width, setWidth] = useState(1920);
	const [height, setHeight] = useState(1080);
	const [brand, setBrand] = useState("");
	const [referenceMode, setReferenceMode] = useState<
		"style_only" | "layout_only" | "hybrid"
	>("hybrid");
	const [jobId, setJobId] = useState<string | null>(null);
	const [progress, setProgress] = useState(0);
	const [status, setStatus] = useState<Status>("idle");
	const [message, setMessage] = useState("");
	const [result, setResult] = useState<GenerationResult | null>(null);
	const [error, setError] = useState<string | null>(null);
	const [showOptions, setShowOptions] = useState(false);
	const wsRef = useRef<WebSocket | null>(null);

	const connectAndSubscribe = useCallback((jid: string) => {
		const wsUrl = getWebSocketUrl("/ws/generation");
		const ws = new WebSocket(wsUrl);
		wsRef.current = ws;

		ws.onopen = () => {
			ws.send(JSON.stringify({ type: "subscribe", job_id: jid }));
		};

		ws.onmessage = (event) => {
			try {
				const data = JSON.parse(event.data as string);
				if (data.type === "progress") {
					setProgress(data.progress ?? 0);
					setStatus((data.status as Status) ?? "queued");
					setMessage(data.message ?? "");
					if (data.result_url) {
						setResult({
							url: data.result_url,
							isMock: data.is_mock ?? false,
							provider: data.provider,
						});
					}
					if (data.status === "failed" && data.message) {
						setError(data.message);
					}
				}
			} catch {
				// ignore parse errors
			}
		};

		ws.onerror = () => setError("WebSocket error");
		ws.onclose = () => {
			wsRef.current = null;
		};
	}, []);

	useEffect(() => {
		return () => {
			if (wsRef.current) wsRef.current.close();
		};
	}, []);

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setError(null);
		setResult(null);
		setJobId(null);
		setProgress(0);
		setStatus("idle");
		setMessage("");

		const trimmed = prompt.trim();
		if (!trimmed) {
			setError("プロンプトを入力してください");
			return;
		}

		try {
			const res = await generateDesign({
				prompt: trimmed,
				resolution: { width, height },
				brand: brand || undefined,
				reference_mode: referenceMode,
			});
			setJobId(res.job_id);
			setStatus("queued");
			setMessage("キューに追加しました");
			connectAndSubscribe(res.job_id);
		} catch (err) {
			setError(
				err instanceof Error
					? err.message
					: "生成リクエストに失敗しました",
			);
		}
	};

	const isRunning =
		status !== "idle" && status !== "completed" && status !== "failed";

	const RESOLUTION_PRESETS = [
		{ label: "1920x1080 (Full HD)", w: 1920, h: 1080 },
		{ label: "1080x1080 (Square)", w: 1080, h: 1080 },
		{ label: "1080x1920 (Story)", w: 1080, h: 1920 },
		{ label: "1200x628 (OGP)", w: 1200, h: 628 },
		{ label: "800x600 (4:3)", w: 800, h: 600 },
	];

	return (
		<div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100">
			<header className="border-b border-zinc-200 dark:border-zinc-800 px-6 py-4">
				<h1 className="text-xl font-semibold">DesignGenerator</h1>
				<nav className="mt-2 text-sm">
					<a
						href="/"
						className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-300"
					>
						ホーム
					</a>
					<span className="mx-2 text-zinc-400">/</span>
					<span className="text-zinc-700 dark:text-zinc-300">
						Generator
					</span>
				</nav>
			</header>

			<main className="max-w-2xl mx-auto px-6 py-10">
				<h2 className="text-2xl font-semibold mb-6">
					AI デザイン生成
				</h2>

				<form onSubmit={handleSubmit} className="space-y-4">
					<div>
						<label
							htmlFor="prompt"
							className="block text-sm font-medium mb-2"
						>
							プロンプト
						</label>
						<textarea
							id="prompt"
							value={prompt}
							onChange={(e) => setPrompt(e.target.value)}
							placeholder="例: ネオンカラーを使ったモダンなログイン画面のUI"
							rows={3}
							className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-4 py-3 text-zinc-900 dark:text-zinc-100 placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-500"
							disabled={isRunning}
						/>
					</div>

					<button
						type="button"
						onClick={() => setShowOptions(!showOptions)}
						className="text-sm text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 transition-colors"
					>
						{showOptions
							? "▲ オプションを閉じる"
							: "▼ 詳細オプション"}
					</button>

					{showOptions && (
						<div className="space-y-4 p-4 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900">
							<div>
								<label className="block text-sm font-medium mb-2">
									解像度プリセット
								</label>
								<div className="flex flex-wrap gap-2">
									{RESOLUTION_PRESETS.map((p) => (
										<button
											key={p.label}
											type="button"
											onClick={() => {
												setWidth(p.w);
												setHeight(p.h);
											}}
											className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
												width === p.w &&
												height === p.h
													? "border-zinc-700 dark:border-zinc-300 bg-zinc-100 dark:bg-zinc-800"
													: "border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-800"
											}`}
										>
											{p.label}
										</button>
									))}
								</div>
								<div className="flex gap-3 mt-2">
									<div className="flex-1">
										<label className="text-xs text-zinc-500">
											幅
										</label>
										<input
											type="number"
											value={width}
											onChange={(e) =>
												setWidth(
													Number(e.target.value),
												)
											}
											min={256}
											max={4096}
											className="w-full rounded border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-1.5 text-sm"
										/>
									</div>
									<div className="flex-1">
										<label className="text-xs text-zinc-500">
											高さ
										</label>
										<input
											type="number"
											value={height}
											onChange={(e) =>
												setHeight(
													Number(e.target.value),
												)
											}
											min={256}
											max={4096}
											className="w-full rounded border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-1.5 text-sm"
										/>
									</div>
								</div>
							</div>

							<div>
								<label className="block text-sm font-medium mb-2">
									参照モード
								</label>
								<select
									value={referenceMode}
									onChange={(e) =>
										setReferenceMode(
											e.target.value as typeof referenceMode,
										)
									}
									className="w-full rounded border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm"
								>
									<option value="hybrid">
										ハイブリッド（スタイル + レイアウト）
									</option>
									<option value="style_only">
										スタイルのみ
									</option>
									<option value="layout_only">
										レイアウトのみ
									</option>
								</select>
							</div>

							<div>
								<label className="block text-sm font-medium mb-2">
									ブランド（任意）
								</label>
								<input
									type="text"
									value={brand}
									onChange={(e) => setBrand(e.target.value)}
									placeholder="例: TechCorp"
									className="w-full rounded border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm"
								/>
							</div>
						</div>
					)}

					<button
						type="submit"
						disabled={isRunning}
						className="w-full rounded-lg bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 font-medium py-3 px-4 hover:bg-zinc-800 dark:hover:bg-zinc-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
					>
						{isRunning ? "生成中..." : "生成する"}
					</button>
				</form>

				{error && (
					<div className="mt-4 p-4 rounded-lg bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-300 text-sm">
						{error}
					</div>
				)}

				{jobId && (
					<div className="mt-8 space-y-4">
						<div className="text-sm text-zinc-500 dark:text-zinc-400">
							Job ID:{" "}
							<code className="bg-zinc-200 dark:bg-zinc-800 px-1 rounded">
								{jobId}
							</code>
						</div>
						<div>
							<div className="flex justify-between text-sm mb-1">
								<span>{message || status}</span>
								<span>{progress}%</span>
							</div>
							<div className="h-2 w-full rounded-full bg-zinc-200 dark:bg-zinc-800 overflow-hidden">
								<div
									className="h-full bg-zinc-700 dark:bg-zinc-300 transition-all duration-300"
									style={{ width: `${progress}%` }}
								/>
							</div>
						</div>
					</div>
				)}

				{result && (
					<div className="mt-8">
						<div className="flex items-center gap-3 mb-3">
							<p className="text-sm font-medium">生成結果</p>
							{result.isMock && (
								<span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 dark:bg-amber-900/40 text-amber-700 dark:text-amber-300">
									MOCK
								</span>
							)}
							{!result.isMock && result.provider && (
								<span className="text-xs px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/40 text-emerald-700 dark:text-emerald-300">
									{result.provider}
								</span>
							)}
						</div>
						{/* eslint-disable-next-line @next/next/no-img-element */}
						<img
							src={result.url}
							alt="Generated design"
							className="w-full rounded-lg border border-zinc-200 dark:border-zinc-800 shadow-sm"
						/>
						<div className="mt-3 flex gap-2">
							<a
								href={result.url}
								target="_blank"
								rel="noopener noreferrer"
								className="text-xs px-3 py-1.5 rounded border border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100 dark:hover:bg-zinc-800 transition-colors"
							>
								原寸大で開く
							</a>
						</div>
					</div>
				)}
			</main>
		</div>
	);
}
