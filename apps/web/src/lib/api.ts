const API_BASE =
	typeof window !== "undefined"
		? (process.env.NEXT_PUBLIC_API_URL || "http://localhost:4000")
		: process.env.NEXT_PUBLIC_API_URL || "http://localhost:4000";

export interface GenerateRequest {
	prompt: string;
	style_reference_ids?: string[];
	layout_reference_ids?: string[];
	brand?: string;
	resolution?: { width: number; height: number };
	reference_mode?: "style_only" | "layout_only" | "hybrid";
}

export interface GenerateResponse {
	job_id: string;
	status: string;
	message: string;
}

export interface SearchResult {
	id: string;
	score: number;
	category: string;
	style_tags: string[];
	caption: string;
	thumbnail_url: string;
}

export interface SearchResponse {
	results: SearchResult[];
	total: number;
	query: string;
}

export async function generateDesign(body: GenerateRequest): Promise<GenerateResponse> {
	const res = await fetch(`${API_BASE}/api/v1/generate`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(body),
	});
	if (!res.ok) throw new Error("Generate request failed");
	return res.json();
}

export async function searchAssets(params: {
	query: string;
	category?: string;
	limit?: number;
}): Promise<SearchResponse> {
	const url = new URL(`${API_BASE}/api/v1/search`);
	url.searchParams.set("query", params.query);
	if (params.category) url.searchParams.set("category", params.category);
	if (params.limit) url.searchParams.set("limit", String(params.limit));
	const res = await fetch(url.toString());
	if (!res.ok) throw new Error("Search request failed");
	return res.json();
}

export interface IngestResponse {
	status: string;
	asset_id?: string;
	filename: string;
	message: string;
	error?: string;
}

export interface IngestBatchResponse {
	status: string;
	count: number;
	results: { filename: string; asset_id?: string; error?: string }[];
}

export async function ingestImage(
	file: File,
	category = "unknown",
	licenseType = "internal",
): Promise<IngestResponse> {
	const form = new FormData();
	form.append("file", file);
	form.append("category", category);
	form.append("license_type", licenseType);

	const res = await fetch(`${API_BASE}/api/v1/ingest`, {
		method: "POST",
		body: form,
	});
	if (!res.ok) throw new Error(`Ingest failed: ${res.status}`);
	return res.json();
}

export async function ingestBatch(files: File[]): Promise<IngestBatchResponse> {
	const form = new FormData();
	for (const f of files) {
		form.append("files", f);
	}
	const res = await fetch(`${API_BASE}/api/v1/ingest/batch`, {
		method: "POST",
		body: form,
	});
	if (!res.ok) throw new Error(`Batch ingest failed: ${res.status}`);
	return res.json();
}

export function getWebSocketUrl(path: string): string {
	const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:4000";
	const wsBase = base.replace(/^http/, "ws");
	return `${wsBase}${path}`;
}

// --- Collector ---

export interface CollectorJobRequest {
	source: string;
	query: string;
	max_pages?: number;
	max_images?: number;
	auto_ingest?: boolean;
}

export interface CollectorJobResponse {
	job_id: string;
	status: string;
}

export interface CollectorJobDetail {
	job_id: string;
	status: string;
	source: string;
	query: string;
	progress: number;
	total_collected: number;
	total_ingested: number;
	auto_ingest: boolean;
	max_pages: number;
	max_images: number;
	error: string | null;
	created_at: string;
	finished_at: string | null;
}

export interface CollectorJobSummary {
	job_id: string;
	status: string;
	source: string;
	query: string;
	progress: number;
	total_collected: number;
	total_ingested: number;
	created_at: string;
	finished_at: string | null;
}

export interface CollectedImageInfo {
	filename: string;
	source_url: string;
	source_domain: string;
	title: string;
	category: string;
	license_type: string;
	ingested: boolean;
}

export interface CollectorImagesResponse {
	job_id: string;
	total: number;
	images: CollectedImageInfo[];
}

export async function createCollectorJob(
	body: CollectorJobRequest,
): Promise<CollectorJobResponse> {
	const res = await fetch(`${API_BASE}/api/v1/collector/jobs`, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify(body),
	});
	if (!res.ok) throw new Error(`Collector job failed: ${res.status}`);
	return res.json();
}

export async function listCollectorJobs(): Promise<CollectorJobSummary[]> {
	const res = await fetch(`${API_BASE}/api/v1/collector/jobs`);
	if (!res.ok) throw new Error(`Failed to list jobs: ${res.status}`);
	return res.json();
}

export async function getCollectorJob(
	jobId: string,
): Promise<CollectorJobDetail> {
	const res = await fetch(`${API_BASE}/api/v1/collector/jobs/${jobId}`);
	if (!res.ok) throw new Error(`Failed to get job: ${res.status}`);
	return res.json();
}

export async function getCollectorJobImages(
	jobId: string,
): Promise<CollectorImagesResponse> {
	const res = await fetch(
		`${API_BASE}/api/v1/collector/jobs/${jobId}/images`,
	);
	if (!res.ok) throw new Error(`Failed to get images: ${res.status}`);
	return res.json();
}
