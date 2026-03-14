"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
	type CollectedImageInfo,
	type CollectorJobDetail,
	type CollectorJobSummary,
	createCollectorJob,
	getCollectorJob,
	getCollectorJobImages,
	listCollectorJobs,
} from "@/lib/api";

const SOURCES = [
	{
		id: "dribbble",
		label: "Dribbble",
		description: "UIデザイン・Webデザインギャラリー",
	},
	{
		id: "behance",
		label: "Behance",
		description: "クリエイティブプロジェクトギャラリー",
	},
	{
		id: "pinterest",
		label: "Pinterest",
		description: "デザインインスピレーション",
	},
	{
		id: "unsplash",
		label: "Unsplash",
		description: "高品質ストック写真（API キー必要）",
	},
	{
		id: "huggingface",
		label: "HuggingFace",
		description: "ML データセットから画像取得",
	},
] as const;

export default function CollectorPage() {
	const [source, setSource] = useState("dribbble");
	const [query, setQuery] = useState("web design");
	const [maxPages, setMaxPages] = useState(5);
	const [maxImages, setMaxImages] = useState(50);
	const [autoIngest, setAutoIngest] = useState(false);

	const [activeJobId, setActiveJobId] = useState<string | null>(null);
	const [jobDetail, setJobDetail] = useState<CollectorJobDetail | null>(null);
	const [images, setImages] = useState<CollectedImageInfo[]>([]);
	const [jobs, setJobs] = useState<CollectorJobSummary[]>([]);
	const [error, setError] = useState<string | null>(null);
	const [submitting, setSubmitting] = useState(false);

	const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

	const stopPolling = useCallback(() => {
		if (pollRef.current) {
			clearInterval(pollRef.current);
			pollRef.current = null;
		}
	}, []);

	const startPolling = useCallback(
		(jobId: string) => {
			stopPolling();
			let errorCount = 0;
			pollRef.current = setInterval(async () => {
				try {
					const detail = await getCollectorJob(jobId);
					errorCount = 0;
					setJobDetail(detail);

					if (
						detail.status === "completed" ||
						detail.status === "failed"
					) {
						stopPolling();
						const imgResp = await getCollectorJobImages(jobId);
						setImages(imgResp.images);
						refreshJobs();
					}
				} catch {
					errorCount++;
					if (errorCount >= 5) {
						stopPolling();
						setJobDetail((prev) =>
							prev
								? {
										...prev,
										status: "failed",
										error: "サービスとの接続が切れました",
									}
								: prev,
						);
					}
				}
			}, 1500);
		},
		[stopPolling],
	);

	const refreshJobs = async () => {
		try {
			const list = await listCollectorJobs();
			setJobs(list.reverse());
		} catch {
			// ignore
		}
	};

	useEffect(() => {
		refreshJobs();
		return stopPolling;
	}, [stopPolling]);

	const handleSubmit = async (e: React.FormEvent) => {
		e.preventDefault();
		setError(null);
		setImages([]);
		setJobDetail(null);
		setSubmitting(true);

		try {
			const resp = await createCollectorJob({
				source,
				query: query.trim(),
				max_pages: maxPages,
				max_images: maxImages,
				auto_ingest: autoIngest,
			});
			setActiveJobId(resp.job_id);
			startPolling(resp.job_id);
		} catch (err) {
			setError(
				err instanceof Error ? err.message : "ジョブの作成に失敗しました",
			);
		} finally {
			setSubmitting(false);
		}
	};

	const viewJob = async (jobId: string) => {
		setActiveJobId(jobId);
		setError(null);
		try {
			const detail = await getCollectorJob(jobId);
			setJobDetail(detail);
			const imgResp = await getCollectorJobImages(jobId);
			setImages(imgResp.images);

			if (detail.status === "running" || detail.status === "pending") {
				startPolling(jobId);
			}
		} catch {
			setError("ジョブ詳細の取得に失敗しました");
		}
	};

	const isRunning =
		jobDetail?.status === "running" || jobDetail?.status === "pending";

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
						デザイン収集
					</span>
				</nav>
			</header>

			<main className="max-w-5xl mx-auto px-6 py-10">
				<h2 className="text-2xl font-semibold mb-8">デザイン収集</h2>

				<div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
					{/* Left: Job Form */}
					<div className="lg:col-span-1 space-y-6">
						<form onSubmit={handleSubmit} className="space-y-5">
							{/* Source */}
							<div>
								<label className="block text-sm font-medium mb-2">
									ソース
								</label>
								<div className="space-y-2">
									{SOURCES.map((s) => (
										<label
											key={s.id}
											className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
												source === s.id
													? "border-zinc-500 bg-zinc-100 dark:bg-zinc-800"
													: "border-zinc-200 dark:border-zinc-800 hover:border-zinc-400 dark:hover:border-zinc-600"
											}`}
										>
											<input
												type="radio"
												name="source"
												value={s.id}
												checked={source === s.id}
												onChange={() =>
													setSource(s.id)
												}
												className="mt-1"
											/>
											<div>
												<div className="text-sm font-medium">
													{s.label}
												</div>
												<div className="text-xs text-zinc-500 dark:text-zinc-400">
													{s.description}
												</div>
											</div>
										</label>
									))}
								</div>
							</div>

							{/* Query */}
							<div>
								<label
									htmlFor="query"
									className="block text-sm font-medium mb-1"
								>
									{source === "huggingface"
										? "データセット名"
										: "検索クエリ"}
								</label>
								<input
									id="query"
									type="text"
									value={query}
									onChange={(e) => setQuery(e.target.value)}
									placeholder={
										source === "huggingface"
											? "user/dataset-name"
											: "web design, UI, etc."
									}
									className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-zinc-500"
								/>
							</div>

							{/* Options */}
							<div className="grid grid-cols-2 gap-3">
								{source !== "huggingface" && (
									<div>
										<label
											htmlFor="maxPages"
											className="block text-xs font-medium mb-1"
										>
											最大ページ数
										</label>
										<input
											id="maxPages"
											type="number"
											min={1}
											max={50}
											value={maxPages}
											onChange={(e) =>
												setMaxPages(
													Number(e.target.value),
												)
											}
											className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm"
										/>
									</div>
								)}
								<div>
									<label
										htmlFor="maxImages"
										className="block text-xs font-medium mb-1"
									>
										最大画像数
									</label>
									<input
										id="maxImages"
										type="number"
										min={1}
										max={1000}
										value={maxImages}
										onChange={(e) =>
											setMaxImages(
												Number(e.target.value),
											)
										}
										className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm"
									/>
								</div>
							</div>

							{/* Auto Ingest */}
							<label className="flex items-center gap-2 cursor-pointer">
								<input
									type="checkbox"
									checked={autoIngest}
									onChange={(e) =>
										setAutoIngest(e.target.checked)
									}
									className="rounded"
								/>
								<span className="text-sm">
									自動的に Ingest サービスに投入
								</span>
							</label>

							{/* Submit */}
							<button
								type="submit"
								disabled={
									submitting || !query.trim() || isRunning
								}
								className="w-full rounded-lg bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 font-medium py-3 px-4 hover:bg-zinc-800 dark:hover:bg-zinc-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
							>
								{submitting
									? "送信中..."
									: isRunning
										? "実行中..."
										: "収集を開始"}
							</button>
						</form>

						{error && (
							<div className="p-3 rounded-lg bg-red-50 dark:bg-red-950/30 text-red-700 dark:text-red-300 text-sm">
								{error}
							</div>
						)}

						{/* Job History */}
						{jobs.length > 0 && (
							<div>
								<h3 className="text-sm font-medium mb-2">
									ジョブ履歴
								</h3>
								<div className="space-y-1 max-h-64 overflow-y-auto">
									{jobs.map((j) => (
										<button
											type="button"
											key={j.job_id}
											onClick={() => viewJob(j.job_id)}
											className={`w-full text-left p-2 rounded-lg text-xs transition-colors ${
												activeJobId === j.job_id
													? "bg-zinc-200 dark:bg-zinc-800"
													: "hover:bg-zinc-100 dark:hover:bg-zinc-900"
											}`}
										>
											<div className="flex justify-between items-center">
												<span className="font-medium">
													{j.source}
												</span>
												<StatusBadge
													status={j.status}
												/>
											</div>
											<div className="text-zinc-500 dark:text-zinc-400 truncate mt-0.5">
												{j.query} ({j.total_collected}{" "}
												枚)
											</div>
										</button>
									))}
								</div>
							</div>
						)}
					</div>

					{/* Right: Progress + Results */}
					<div className="lg:col-span-2 space-y-6">
						{/* Progress */}
						{jobDetail && (
							<div className="rounded-xl border border-zinc-200 dark:border-zinc-800 p-5 space-y-4">
								<div className="flex items-center justify-between">
									<h3 className="text-sm font-semibold">
										ジョブ進捗
									</h3>
									<StatusBadge status={jobDetail.status} />
								</div>

								<div className="grid grid-cols-3 gap-4 text-center">
									<Stat
										label="収集済み"
										value={jobDetail.total_collected}
									/>
									<Stat
										label="Ingest済み"
										value={jobDetail.total_ingested}
									/>
									<Stat
										label="進捗"
										value={`${jobDetail.progress}%`}
									/>
								</div>

								<div className="h-2 w-full rounded-full bg-zinc-200 dark:bg-zinc-800 overflow-hidden">
									<div
										className={`h-full transition-all duration-300 ${
											jobDetail.status === "failed"
												? "bg-red-500"
												: jobDetail.status ===
													  "completed"
													? "bg-green-500 dark:bg-green-400"
													: "bg-zinc-700 dark:bg-zinc-300"
										}`}
										style={{
											width: `${jobDetail.progress}%`,
										}}
									/>
								</div>

								{jobDetail.error && (
									<p className="text-sm text-red-500">
										{jobDetail.error}
									</p>
								)}

								<div className="text-xs text-zinc-500 dark:text-zinc-400 space-y-1">
									<p>
										ソース: {jobDetail.source} / クエリ:{" "}
										{jobDetail.query}
									</p>
									<p>
										Job ID:{" "}
										<code className="bg-zinc-200 dark:bg-zinc-800 px-1 rounded">
											{jobDetail.job_id.slice(0, 12)}...
										</code>
									</p>
								</div>
							</div>
						)}

						{/* Image Gallery */}
						{images.length > 0 && (
							<div>
								<h3 className="text-sm font-semibold mb-3">
									収集済み画像 ({images.length} 枚)
								</h3>
								<div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
									{images.map((img, i) => (
										<div
											key={`${img.filename}-${i}`}
											className="group relative rounded-lg border border-zinc-200 dark:border-zinc-800 overflow-hidden bg-zinc-100 dark:bg-zinc-900"
										>
											<div className="aspect-square flex items-center justify-center p-2">
												<div className="text-center">
													<svg
														className="w-8 h-8 mx-auto text-zinc-400 mb-1"
														fill="none"
														viewBox="0 0 24 24"
														stroke="currentColor"
														strokeWidth={1.5}
													>
														<path
															strokeLinecap="round"
															strokeLinejoin="round"
															d="m2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0 0 22.5 18.75V5.25A2.25 2.25 0 0 0 20.25 3H3.75A2.25 2.25 0 0 0 1.5 5.25v13.5A2.25 2.25 0 0 0 3.75 21Z"
														/>
													</svg>
													<p className="text-xs text-zinc-500 truncate max-w-[120px]">
														{img.filename}
													</p>
												</div>
											</div>
											<div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col justify-end p-2">
												<p className="text-xs text-white truncate">
													{img.title || img.filename}
												</p>
												<div className="flex items-center gap-1 mt-1">
													<span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-700 text-zinc-300">
														{img.source_domain}
													</span>
													{img.ingested && (
														<span className="text-[10px] px-1.5 py-0.5 rounded bg-green-700 text-green-200">
															ingested
														</span>
													)}
												</div>
											</div>
										</div>
									))}
								</div>
							</div>
						)}

						{/* Empty state */}
						{!jobDetail && images.length === 0 && (
							<div className="flex flex-col items-center justify-center py-20 text-zinc-400">
								<svg
									className="w-16 h-16 mb-4"
									fill="none"
									viewBox="0 0 24 24"
									stroke="currentColor"
									strokeWidth={1}
								>
									<path
										strokeLinecap="round"
										strokeLinejoin="round"
										d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5m6 4.125l2.25 2.25m0 0l2.25 2.25M12 13.875l2.25-2.25M12 13.875l-2.25 2.25M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z"
									/>
								</svg>
								<p className="text-sm">
									左のフォームからソースを選択して収集を開始してください
								</p>
							</div>
						)}
					</div>
				</div>
			</main>
		</div>
	);
}

function StatusBadge({ status }: { status: string }) {
	const styles: Record<string, string> = {
		pending:
			"bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300",
		running:
			"bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
		completed:
			"bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
		failed: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
	};

	return (
		<span
			className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${styles[status] || "bg-zinc-200 text-zinc-600"}`}
		>
			{status}
		</span>
	);
}

function Stat({ label, value }: { label: string; value: number | string }) {
	return (
		<div>
			<div className="text-lg font-semibold">{value}</div>
			<div className="text-xs text-zinc-500 dark:text-zinc-400">
				{label}
			</div>
		</div>
	);
}
