import { ScanResponse, ApiErrorShape } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Case: NEXT_PUBLIC_API_URL was never set (e.g. deployed without configuring
// env vars) — silently falling back to localhost would mean every request
// fails with a confusing generic network error. Warn once in the console so
// a developer debugging a broken deploy has an immediate lead, without
// showing anything to the end user (this is a dev/ops signal, not a UX one).
if (typeof window !== "undefined" && !process.env.NEXT_PUBLIC_API_URL) {
  // eslint-disable-next-line no-console
  console.warn(
    "NEXT_PUBLIC_API_URL is not set — defaulting to http://localhost:8000. " +
      "Set it in .env.local (see .env.local.example) for this to work outside local dev."
  );
}

// Different endpoints legitimately take different amounts of time:
// - text: one DB pass + a couple of LLM calls — fast.
// - image: OCR (Groq vision) first, then the same pipeline — slower.
// - product-name: web search + extraction + the same pipeline — slowest,
//   and most likely to hit a genuinely slow/hung external dependency.
const TIMEOUT_MS = {
  text: 30_000,
  image: 60_000,
  productName: 60_000,
} as const;

/**
 * Case: the backend never responds at all (hung connection, dead server,
 * firewall silently dropping packets). Without an explicit timeout, fetch()
 * only gives up based on the browser/OS's own TCP timeout, which can be
 * minutes — the UI would just spin forever. AbortController gives us a
 * predictable, much shorter cutoff with a clear, distinguishable error.
 */
async function fetchWithTimeout(url: string, options: RequestInit, timeoutMs: number): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (err) {
    // Case: the abort fired — surface a specific, friendly message instead
    // of the raw "AbortError" / "The user aborted a request" browser text.
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error(
        "The request took too long and timed out. The server may be waking up " +
          "(common on free hosting) — please try again in a moment."
      );
    }
    // Case: genuine network failure — offline, DNS failure, CORS block, or
    // the backend host is simply unreachable. All of these surface from
    // fetch() as a generic TypeError ("Failed to fetch" / "Load failed")
    // with no further detail — translate it into something actionable.
    if (err instanceof TypeError) {
      throw new Error(
        "Couldn't reach the server. Check your internet connection, or the " +
          "server may be temporarily down — please try again."
      );
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Case: the response is a 4xx/5xx. FastAPI's normal shape is
 * `{"detail": "some string"}`, but validation errors from Pydantic use
 * `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` — an ARRAY of
 * objects, not a string. Rendering that directly in a React <p> would throw
 * "Objects are not valid as a React child" and crash the error UI itself.
 * Handle every shape defensively: string, array-of-objects, array-of-strings,
 * or a body that isn't JSON at all (e.g. an HTML error page from a proxy/host
 * in front of the API, or a completely empty body).
 */
async function parseErrorDetail(res: Response): Promise<string> {
  let body: unknown;
  try {
    body = await res.json();
  } catch {
    // Case: body isn't valid JSON at all (HTML error page, empty body, etc).
    return statusFallbackMessage(res.status);
  }

  const detail = (body as ApiErrorShape | undefined)?.detail;

  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0];
    if (typeof first === "string") return first;
    if (first && typeof first === "object" && "msg" in first) {
      return String((first as { msg: unknown }).msg);
    }
  }

  return statusFallbackMessage(res.status);
}

/** Case: no usable message from the body at all — fall back to a message keyed off the status code, since a bare "Request failed (500)" isn't very actionable for a non-technical user. */
function statusFallbackMessage(status: number): string {
  if (status === 429) return "Too many requests right now — please wait a moment and try again.";
  if (status === 502 || status === 503) return "The server is temporarily unavailable. Please try again shortly.";
  if (status === 504) return "The server took too long to respond. Please try again.";
  if (status >= 500) return "Something went wrong on our end. Please try again.";
  if (status === 413) return "That file is too large for the server to accept.";
  return `Request failed (${status}). Please try again.`;
}

/**
 * Case: the server returned 200 OK but the body isn't valid JSON, or is
 * JSON that doesn't actually look like a ScanResponse (e.g. a proxy
 * injected an HTML page on top of a 200, or a future API mismatch). Without
 * this check, a malformed-but-"successful" response would crash deep inside
 * ResultCard's rendering instead of failing cleanly here with a clear
 * message and a retry option.
 */
async function parseScanResponse(res: Response): Promise<ScanResponse> {
  let data: unknown;
  try {
    data = await res.json();
  } catch {
    throw new Error("Received an unexpected response from the server. Please try again.");
  }

  if (
    !data ||
    typeof data !== "object" ||
    !Array.isArray((data as Partial<ScanResponse>).results) ||
    typeof (data as Partial<ScanResponse>).safety_score !== "number"
  ) {
    throw new Error("Received an incomplete response from the server. Please try again.");
  }

  return data as ScanResponse;
}

export async function scanText(ingredientsText: string, productName?: string): Promise<ScanResponse> {
  const res = await fetchWithTimeout(
    `${API_URL}/scan/text`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ingredients_text: ingredientsText,
        product_name: productName || undefined,
      }),
    },
    TIMEOUT_MS.text
  );

  if (!res.ok) throw new Error(await parseErrorDetail(res));
  return parseScanResponse(res);
}

export async function scanByProductName(productName: string): Promise<ScanResponse> {
  const res = await fetchWithTimeout(
    `${API_URL}/scan/product-name`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product_name: productName }),
    },
    TIMEOUT_MS.productName
  );

  if (!res.ok) throw new Error(await parseErrorDetail(res));
  return parseScanResponse(res);
}

export async function scanImage(file: File, productName?: string): Promise<ScanResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (productName) formData.append("product_name", productName);

  const res = await fetchWithTimeout(
    `${API_URL}/scan/image`,
    { method: "POST", body: formData },
    TIMEOUT_MS.image
  );

  if (!res.ok) throw new Error(await parseErrorDetail(res));
  return parseScanResponse(res);
}
