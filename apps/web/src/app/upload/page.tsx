"use client";

import { useCallback, useRef, useState } from "react";
import { ingestImage } from "@/lib/api";

interface UploadResult {
	filename: string;
	asset_id?: string;
	status: "uploading" | "done" | "error";
	message?: string;
}

export default function UploadPage() {
	const [results, setResults] = useState<UploadResult[]>([]);
	const [dragOver, setDragOver] = useState(false);
	const [category, setCategory] = useState("banner");
	const fileInputRef = useRef<HTMLInputElement>(null);

	const uploadFile = useCallback(
		async (file: File) => {
			const entry: UploadResult = { filename: file.name, status: "uploading" };
			setResults((prev) => [...prev, entry]);

			try {
				const res = await ingestImage(file, category);
				setResults((prev) =>
					prev.map((r) =>
						r.filename === file.name && r.status === "uploading"
							? { ...r, status: "done", asset_id: res.asset_id, message: res.message }
							: r,
					),
				);
			} catch (err) {
				setResults((prev) =>
					prev.map((r) =>
						r.filename === file.name && r.status === "uploading"
							? { ...r, status: "error", message: err instanceof Error ? err.message : "失敗" }
							: r,
					),
				);
			}
		},
		[category],
	);

	const handleFiles = useCallback(
		(files: FileList | null) => {
			if (!files) return;
			Array.from(files).forEach((f) => {
				if (f.type.startsWith("image/")) uploadFile(f);
			});
		},
		[uploadFile],
	);

	const handleDrop = useCallback(
		(e: React.DragEvent) => {
			e.preventDefault();
			setDragOver(false);
			handleFiles(e.dataTransfer.files);
		},
		[handleFiles],
	);

	const doneCount = results.filter((r) => r.status === "done").length;
	const errorCount = results.filter((r) => r.status === "error").length;

	return (
		<div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100">
			<header className="border-b border-zinc-200 dark:border-zinc-800 px-6 py-4">
				<h1 className="text-xl font-semibold">DesignGenerator</h1>
				<nav className="mt-2 text-sm">
					<a href="/" className="text-zinc-500 hover:text-zinc-900 dark:hover:text-zinc-300">
						ホーム
					</a>
					<span className="mx-2 text-zinc-400">/</span>
					<span className="text-zinc-700 dark:text-zinc-300">アップロード</span>
				</nav>
			</header>

			<main className="max-w-2xl mx-auto px-6 py-10">
				<h2 className="text-2xl font-semibold mb-6">画像アップロード</h2>

				<div className="mb-4">
					<label htmlFor="category" className="block text-sm font-medium mb-1">
						カテゴリ
					</label>
					<select
						id="category"
						value={category}
						onChange={(e) => setCategory(e.target.value)}
						className="rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2 text-sm"
					>
						<option value="banner">バナー</option>
						<option value="ui">UI</option>
						<option value="icon">アイコン</option>
						<option value="illustration">イラスト</option>
						<option value="photo">写真</option>
						<option value="unknown">その他</option>
					</select>
				</div>

				<div
					onDragOver={(e) => {
						e.preventDefault();
						setDragOver(true);
					}}
					onDragLeave={() => setDragOver(false)}
					onDrop={handleDrop}
					onClick={() => fileInputRef.current?.click()}
					className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-12 cursor-pointer transition-colors ${
						dragOver
							? "border-zinc-500 bg-zinc-100 dark:bg-zinc-800"
							: "border-zinc-300 dark:border-zinc-700 hover:border-zinc-400 dark:hover:border-zinc-600"
					}`}
				>
					<svg
						className="w-10 h-10 text-zinc-400 mb-3"
						fill="none"
						viewBox="0 0 24 24"
						stroke="currentColor"
						strokeWidth={1.5}
					>
						<path
							strokeLinecap="round"
							strokeLinejoin="round"
							d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
						/>
					</svg>
					<p className="text-sm text-zinc-600 dark:text-zinc-400">
						ここにドラッグ&ドロップ、またはクリックしてファイルを選択
					</p>
					<p className="text-xs text-zinc-400 mt-1">PNG, JPG, WebP に対応</p>
					<input
						ref={fileInputRef}
						type="file"
						accept="image/*"
						multiple
						className="hidden"
						onChange={(e) => handleFiles(e.target.files)}
					/>
				</div>

				{results.length > 0 && (
					<div className="mt-6 space-y-2">
						<p className="text-sm text-zinc-500">
							{doneCount} 件完了
							{errorCount > 0 && ` / ${errorCount} 件エラー`}
						</p>
						<div className="divide-y divide-zinc-200 dark:divide-zinc-800 rounded-lg border border-zinc-200 dark:border-zinc-800 overflow-hidden">
							{results.map((r, i) => (
								<div
									key={`${r.filename}-${i}`}
									className="flex items-center justify-between px-4 py-3 text-sm"
								>
									<span className="truncate max-w-[200px]">{r.filename}</span>
									{r.status === "uploading" && (
										<span className="text-zinc-400">アップロード中...</span>
									)}
									{r.status === "done" && (
										<span className="text-green-600 dark:text-green-400">
											{r.asset_id?.slice(0, 8)}...
										</span>
									)}
									{r.status === "error" && (
										<span className="text-red-500">{r.message}</span>
									)}
								</div>
							))}
						</div>
					</div>
				)}
			</main>
		</div>
	);
}
