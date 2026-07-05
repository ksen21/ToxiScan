import { ScanResponse, ApiErrorShape } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function parseErrorDetail(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as ApiErrorShape;
    return body.detail || `Request failed (${res.status})`;
  } catch {
    return `Request failed (${res.status})`;
  }
}

export async function scanText(
  ingredientsText: string,
  productName?: string
): Promise<ScanResponse> {
  const res = await fetch(`${API_URL}/scan/text`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      ingredients_text: ingredientsText,
      product_name: productName || undefined,
    }),
  });

  if (!res.ok) {
    throw new Error(await parseErrorDetail(res));
  }
  return res.json();
}

export async function scanImage(
  file: File,
  productName?: string
): Promise<ScanResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (productName) formData.append("product_name", productName);

  const res = await fetch(`${API_URL}/scan/image`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    throw new Error(await parseErrorDetail(res));
  }
  return res.json();
}
