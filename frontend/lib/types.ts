// Mirrors backend/models/schemas.py — keep in sync with ScanResponse / IngredientResult.

export type SeverityLevel = "low" | "moderate" | "high" | "critical";

export type VerificationStatus = "verified_safe" | "uncertain";

export interface IngredientResult {
  ingredient: string;
  matched_chemical: string | null;
  severity: SeverityLevel | null;
  concerns: string[];
  is_flagged: boolean;
  research_url: string | null;
  // Only set for non-flagged ingredients (see services/ingredient_verify.py).
  // null means "not verified" — treat the same as "uncertain", never as safe.
  verification_status: VerificationStatus | null;
  verification_note: string | null;
}

export interface ScanResponse {
  product_name: string | null;
  total_ingredients: number;
  flagged_count: number;
  safety_score: number; // 0-100
  score_out_of_10: number; // e.g. 6.6
  star_rating: number; // e.g. 3.3, out of 5
  safety_label: "Safe" | "Moderate" | "Risky" | "Dangerous" | string;
  results: IngredientResult[];
  scanned_at: string;
  // Transparency note when a fallback path was used (e.g. ingredients came
  // from a web search using a product name read off a photo, not directly
  // from that photo). null on the normal, direct paths.
  source_note: string | null;
}

export interface ApiErrorShape {
  detail: string | Array<string | { msg: unknown; [key: string]: unknown }>;
}
