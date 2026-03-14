export interface BoundingBox {
	x: number;
	y: number;
	width: number;
	height: number;
	label?: string;
}

export interface TypographySpec {
	font_family: string;
	font_weight: number;
	font_size: number;
	line_height?: number;
	letter_spacing?: number;
}

export interface DecomposedQuery {
	layout_intent: string;
	style_descriptors: string[];
	typography_spec?: TypographySpec;
	color_constraints: string[];
	brand_guidelines?: string;
	spatial_constraints?: BoundingBox[];
	reference_mode: "style_only" | "layout_only" | "hybrid";
}

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
	status: "queued" | "processing" | "completed" | "failed";
	result_url?: string;
	decomposed_query?: DecomposedQuery;
	reference_images?: string[];
	metadata?: Record<string, unknown>;
}

export interface SearchRequest {
	query: string;
	category?: string;
	style_tags?: string[];
	color_palette?: string[];
	brand?: string;
	license_type?: string;
	limit?: number;
}

export interface SearchResult {
	id: string;
	score: number;
	asset: DesignAsset;
}

export interface DesignAsset {
	id: string;
	file_path: string;
	thumbnail_url: string;
	category: string;
	style_tags: string[];
	color_palette: string[];
	typography: string;
	caption: string;
	resolution: string;
	license_type: string;
	brand?: string;
	created_at: string;
}

export interface DesignToken {
	id: string;
	name: string;
	type: "color" | "typography" | "spacing" | "border-radius" | "shadow";
	value: string | number | Record<string, unknown>;
	category: string;
	source_asset_id?: string;
}

export interface GenerationProgress {
	job_id: string;
	progress: number;
	status: "queued" | "searching" | "generating" | "post_processing" | "completed" | "failed";
	message: string;
	result_url?: string;
	error?: string;
}

export interface ModelRouteConfig {
	model_name: string;
	provider: "local" | "fal_ai" | "adobe_firefly" | "recraft";
	reason: string;
}
