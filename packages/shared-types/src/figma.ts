import type { DesignToken } from "./api";

export interface TokenReviewPayload {
	generation_id: string;
	source_asset_id: string;
	extracted_tokens: DesignToken[];
	preview_image_url: string;
	extracted_at: string;
}

export interface TokenApproval {
	generation_id: string;
	approved_tokens: DesignToken[];
	rejected_token_ids: string[];
	modified_tokens: DesignToken[];
	approved_by: string;
	approved_at: string;
	sync_targets: SyncTarget[];
}

export interface SyncTarget {
	type: "figma_variables" | "github_pr" | "css_variables" | "tailwind_config";
	target_id: string;
	status: "pending" | "synced" | "failed";
}
