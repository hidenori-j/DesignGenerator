"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
	type BulkIngestStatus,
	type CollectionStats,
	type LocalFilesResponse,
	bulkIngestLocalFiles,
	getBulkIngestStatus,
	getCollectionStats,
	getLocalFiles,
	resetCollection,
} from "@/lib/api";

type DedupMode = "skip" | "overwrite";

export default function SettingsPage() {
	const [stats, setStats] = useState<CollectionStats | null>(null);
	const [statsLoading, setStatsLoading] = useState(true);
	const [statsError, setStatsError] = useState("");

	const [resetConfirm, setResetConfirm] = useState("");
	const [resetting, setResetting] = useState(false);
	const [resetResult, setResetResult] = useState<{
		ok: boolean;
		message: string;
	} | null>(null);

	const [localFiles, setLocalFiles] = useState<LocalFilesResponse | null>(null);
	const [filesLoading, setFilesLoading] = useState(true);

	const [ingestCategory, setIngestCategory] = useState("unknown");
	const [ingestDedup, setIngestDedup] = useState<DedupMode>("skip");
	const [ingestSource, setIngestSource] = useState<string>("");
	const [bulkJob, setBulkJob] = useState<BulkIngestStatus | null>(null);
	const [ingesting, setIngesting] = useState(false);
	const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

	const loadStats = useCallback(async () => {
		setStatsLoading(true);
		setStatsError("");
		try {
			const s = await getCollectionStats();
			setStats(s);
		} catch (e) {
			setStatsError(e instanceof Error ? e.message : "Failed to load stats");
		} finally {
			setStatsLoading(false);
		}
	}, []);

	const loadLocalFiles = useCallback(async () => {
		setFilesLoading(true);
		try {
			const f = await getLocalFiles();
			setLocalFiles(f);
		} catch {
			setLocalFiles(null);
		} finally {
			setFilesLoading(false);
		}
	}, []);

	useEffect(() => {
		loadStats();
		loadLocalFiles();
	}, [loadStats, loadLocalFiles]);

	useEffect(() => {
		return () => {
			if (pollRef.current) clearInterval(pollRef.current);
		};
	}, []);

	const handleReset = async () => {
		if (resetConfirm !== "RESET") return;
		setResetting(true);
		setResetResult(null);
		try {
			const res = await resetCollection();
			setResetResult({ ok: true, message: res.message });
			setResetConfirm("");
			await loadStats();
		} catch (e) {
			setResetResult({
				ok: false,
				message: e instanceof Error ? e.message : "Reset failed",
			});
		} finally {
			setResetting(false);
		}
	};

	const handleBulkIngest = async () => {
		setIngesting(true);
		setBulkJob(null);
		try {
			const res = await bulkIngestLocalFiles({
				source: ingestSource || undefined,
				category: ingestCategory,
				dedup: ingestDedup,
			});
			const jobId = res.job_id;

			pollRef.current = setInterval(async () => {
				try {
					const status = await getBulkIngestStatus(jobId);
					setBulkJob(status);
					if (status.status === "completed") {
						if (pollRef.current) clearInterval(pollRef.current);
						setIngesting(false);
						await loadStats();
					}
				} catch {
					if (pollRef.current) clearInterval(pollRef.current);
					setIngesting(false);
				}
			}, 1000);
		} catch (e) {
			setIngesting(false);
			setBulkJob({
				job_id: "",
				status: "failed",
				total: 0,
				ingested: 0,
				skipped: 0,
				failed: 0,
				progress: 0,
				category: ingestCategory,
				dedup: ingestDedup,
				source: ingestSource || "all",
				errors: [
					{
						file: "-",
						error: e instanceof Error ? e.message : "Request failed",
					},
				],
				created_at: "",
				finished_at: null,
			});
		}
	};

	const sourceKeys = localFiles ? Object.keys(localFiles.sources) : [];

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
					<span className="text-zinc-700 dark:text-zinc-300">設定</span>
				</nav>
			</header>

			<main className="max-w-3xl mx-auto px-6 py-10 space-y-12">
				{/* ===== Section A: Qdrant Collection ===== */}
				<section>
					<h2 className="text-2xl font-semibold mb-6">
						Qdrant データ管理
					</h2>

					{/* Stats */}
					<div className="rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 mb-6">
						<h3 className="text-sm font-medium text-zinc-500 dark:text-zinc-400 mb-3">
							コレクション統計
						</h3>
						{statsLoading ? (
							<p className="text-sm text-zinc-400">読み込み中...</p>
						) : statsError ? (
							<p className="text-sm text-red-500">{statsError}</p>
						) : stats ? (
							<div className="grid grid-cols-3 gap-4">
								<div>
									<p className="text-2xl font-bold">
										{stats.points_count.toLocaleString()}
									</p>
									<p className="text-xs text-zinc-500">ポイント数</p>
								</div>
								<div>
									<p className="text-2xl font-bold">
										{stats.vectors_count.toLocaleString()}
									</p>
									<p className="text-xs text-zinc-500">ベクトル数</p>
								</div>
								<div>
									<p className="text-2xl font-bold">{stats.status}</p>
									<p className="text-xs text-zinc-500">ステータス</p>
								</div>
							</div>
						) : null}
						<button
							type="button"
							onClick={loadStats}
							className="mt-3 text-xs text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 underline"
						>
							再読み込み
						</button>
					</div>

					{/* Reset */}
					<div className="rounded-xl border border-red-200 dark:border-red-900/50 p-6">
						<h3 className="text-sm font-medium text-red-600 dark:text-red-400 mb-2">
							コレクションリセット
						</h3>
						<p className="text-sm text-zinc-600 dark:text-zinc-400 mb-4">
							design_assets コレクションの全データを削除し、空の状態で再作成します。
							この操作は取り消せません。
						</p>
						<div className="flex items-center gap-3">
							<input
								type="text"
								placeholder='確認のため "RESET" と入力'
								value={resetConfirm}
								onChange={(e) => setResetConfirm(e.target.value)}
								className="flex-1 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm"
							/>
							<button
								type="button"
								onClick={handleReset}
								disabled={resetConfirm !== "RESET" || resetting}
								className="rounded-lg bg-red-600 text-white px-4 py-2 text-sm font-medium disabled:opacity-40 hover:bg-red-700 transition-colors"
							>
								{resetting ? "リセット中..." : "リセット実行"}
							</button>
						</div>
						{resetResult && (
							<p
								className={`mt-3 text-sm ${resetResult.ok ? "text-green-600 dark:text-green-400" : "text-red-500"}`}
							>
								{resetResult.message}
							</p>
						)}
					</div>
				</section>

				{/* ===== Section B: Bulk Ingest ===== */}
				<section>
					<h2 className="text-2xl font-semibold mb-6">
						収集済みファイルの一括登録
					</h2>

					{/* File summary */}
					<div className="rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 mb-6">
						<h3 className="text-sm font-medium text-zinc-500 dark:text-zinc-400 mb-3">
							ローカルファイル一覧
						</h3>
						{filesLoading ? (
							<p className="text-sm text-zinc-400">読み込み中...</p>
						) : localFiles && localFiles.total > 0 ? (
							<>
								<div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-4">
									{sourceKeys.map((src) => (
										<div
											key={src}
											className="rounded-lg border border-zinc-200 dark:border-zinc-700 p-3"
										>
											<p className="text-lg font-bold">
												{localFiles.sources[src].toLocaleString()}
											</p>
											<p className="text-xs text-zinc-500">{src}</p>
										</div>
									))}
								</div>
								<p className="text-sm text-zinc-500">
									合計: {localFiles.total.toLocaleString()} ファイル
								</p>
							</>
						) : (
							<p className="text-sm text-zinc-400">
								収集済みファイルがありません。先にデザイン収集を実行してください。
							</p>
						)}
						<button
							type="button"
							onClick={loadLocalFiles}
							className="mt-3 text-xs text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 underline"
						>
							再読み込み
						</button>
					</div>

					{/* Ingest controls */}
					{localFiles && localFiles.total > 0 && (
						<div className="rounded-xl border border-zinc-200 dark:border-zinc-800 p-6">
							<h3 className="text-sm font-medium text-zinc-500 dark:text-zinc-400 mb-4">
								一括登録オプション
							</h3>
							<div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
								<div>
									<label
										htmlFor="ingest-source"
										className="block text-xs font-medium mb-1"
									>
										ソース
									</label>
									<select
										id="ingest-source"
										value={ingestSource}
										onChange={(e) => setIngestSource(e.target.value)}
										className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm"
									>
										<option value="">全て</option>
										{sourceKeys.map((src) => (
											<option key={src} value={src}>
												{src} ({localFiles.sources[src]})
											</option>
										))}
									</select>
								</div>
								<div>
									<label
										htmlFor="ingest-category"
										className="block text-xs font-medium mb-1"
									>
										カテゴリ
									</label>
									<select
										id="ingest-category"
										value={ingestCategory}
										onChange={(e) => setIngestCategory(e.target.value)}
										className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm"
									>
										<option value="banner">バナー</option>
										<option value="ui">UI</option>
										<option value="icon">アイコン</option>
										<option value="illustration">イラスト</option>
										<option value="photo">写真</option>
										<option value="unknown">その他</option>
									</select>
								</div>
								<div>
									<label
										htmlFor="ingest-dedup"
										className="block text-xs font-medium mb-1"
									>
										重複処理
									</label>
									<select
										id="ingest-dedup"
										value={ingestDedup}
										onChange={(e) =>
											setIngestDedup(e.target.value as DedupMode)
										}
										className="w-full rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm"
									>
										<option value="skip">スキップ（重複を無視）</option>
										<option value="overwrite">上書き（既存を更新）</option>
									</select>
								</div>
							</div>

							<button
								type="button"
								onClick={handleBulkIngest}
								disabled={ingesting}
								className="rounded-lg bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 font-medium py-2.5 px-6 text-sm hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-colors disabled:opacity-40"
							>
								{ingesting
									? "登録中..."
									: `${ingestSource || "全ファイル"}を Qdrant に登録`}
							</button>

							{/* Progress */}
							{bulkJob && (
								<div className="mt-6 space-y-3">
									<div className="w-full bg-zinc-200 dark:bg-zinc-800 rounded-full h-2">
										<div
											className="bg-zinc-900 dark:bg-zinc-100 h-2 rounded-full transition-all duration-300"
											style={{ width: `${bulkJob.progress}%` }}
										/>
									</div>
									<div className="flex items-center justify-between text-sm">
										<span className="text-zinc-500">
											{bulkJob.progress}%
										</span>
										<span
											className={
												bulkJob.status === "completed"
													? "text-green-600 dark:text-green-400"
													: bulkJob.status === "failed"
														? "text-red-500"
														: "text-zinc-500"
											}
										>
											{bulkJob.status === "completed"
												? "完了"
												: bulkJob.status === "failed"
													? "失敗"
													: "処理中..."}
										</span>
									</div>
									<div className="grid grid-cols-3 gap-3 text-center">
										<div className="rounded-lg border border-zinc-200 dark:border-zinc-700 p-2">
											<p className="text-lg font-bold text-green-600 dark:text-green-400">
												{bulkJob.ingested}
											</p>
											<p className="text-xs text-zinc-500">登録</p>
										</div>
										<div className="rounded-lg border border-zinc-200 dark:border-zinc-700 p-2">
											<p className="text-lg font-bold text-yellow-600 dark:text-yellow-400">
												{bulkJob.skipped}
											</p>
											<p className="text-xs text-zinc-500">
												スキップ
											</p>
										</div>
										<div className="rounded-lg border border-zinc-200 dark:border-zinc-700 p-2">
											<p className="text-lg font-bold text-red-500">
												{bulkJob.failed}
											</p>
											<p className="text-xs text-zinc-500">失敗</p>
										</div>
									</div>
									{bulkJob.errors.length > 0 && (
										<details className="text-sm">
											<summary className="cursor-pointer text-red-500">
												エラー詳細 ({bulkJob.errors.length})
											</summary>
											<ul className="mt-2 space-y-1 text-xs text-zinc-500">
												{bulkJob.errors.map((err) => (
													<li key={`${err.file}-${err.error}`}>
														<span className="font-mono">
															{err.file}
														</span>
														: {err.error}
													</li>
												))}
											</ul>
										</details>
									)}
								</div>
							)}
						</div>
					)}
				</section>
			</main>
		</div>
	);
}
