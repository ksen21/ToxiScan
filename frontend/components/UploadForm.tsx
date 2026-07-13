"use client";

import { useEffect, useRef, useState } from "react";

interface UploadFormProps {
  onSubmitText: (ingredientsText: string, productName: string) => void;
  onSubmitImage: (file: File, productName: string) => void;
  onSubmitProductName: (productName: string) => void;
  disabled?: boolean;
}

const MAX_IMAGE_MB = 8;
const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp"];
const ALLOWED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"];
const HEIC_EXTENSIONS = [".heic", ".heif"];
const MAX_TEXT_LENGTH = 20000; // matches backend ScanRequest.ingredients_text max_length
const MAX_PRODUCT_NAME_LENGTH = 300; // matches backend max_length

function getExtension(filename: string): string {
  const dot = filename.lastIndexOf(".");
  return dot >= 0 ? filename.slice(dot).toLowerCase() : "";
}

// Case: pure punctuation/whitespace input like ",,, ,," or "..." technically
// clears a bare `.trim().length >= 3` check but has no real content — require
// at least one letter or digit somewhere in the string.
function hasRealContent(value: string): boolean {
  return /[a-zA-Z0-9]/.test(value);
}

export default function UploadForm({
  onSubmitText,
  onSubmitImage,
  onSubmitProductName,
  disabled,
}: UploadFormProps) {
  const [mode, setMode] = useState<"text" | "image" | "name">("name");
  const [productName, setProductName] = useState("");
  const [ingredientsText, setIngredientsText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  // Case: user double-clicks/double-taps "Scan ingredients" before the
  // parent's `disabled` prop has a chance to re-render — a local lock closes
  // that race window immediately, without waiting on a parent state update.
  const [justSubmitted, setJustSubmitted] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Case: component unmounts (or the picked file changes) while an object
  // URL from a previous preview is still alive — revoke it so we don't leak
  // memory across repeated "pick a photo, change my mind, pick another" cycles.
  useEffect(() => {
    return () => {
      if (preview) URL.revokeObjectURL(preview);
    };
  }, [preview]);

  // Case: `disabled` becomes false again (parent finished loading, or the
  // user hit "try again") — release our local submit lock so the form is
  // usable for the next attempt.
  useEffect(() => {
    if (!disabled) setJustSubmitted(false);
  }, [disabled]);

  function handleFile(candidate: File | undefined) {
    if (!candidate) return; // Case: drag event with no actual file (e.g. dragged text/a link)

    const ext = getExtension(candidate.name);

    // Case: 0-byte file — a corrupted capture or a placeholder the OS
    // sometimes creates. Reject before it ever reaches the network.
    if (candidate.size === 0) {
      setFileError("That file appears to be empty. Please choose a different photo.");
      return;
    }

    // Case: iPhones default to HEIC/HEIF, which browsers often don't even
    // report a recognizable `type` for (empty string) and our OCR model
    // can't read — give a specific, actionable message instead of the
    // generic "use JPEG/PNG/WebP" that doesn't explain *why* it failed.
    if (HEIC_EXTENSIONS.includes(ext) || candidate.type === "image/heic" || candidate.type === "image/heif") {
      setFileError(
        "HEIC photos aren't supported yet. On iPhone: Settings → Camera → Formats → " +
          "\"Most Compatible\" (saves new photos as JPEG), or choose \"Actual Size\" when sharing this photo."
      );
      return;
    }

    // Case: some mobile browsers/webviews report an empty `type` for camera
    // captures even though the file is a perfectly normal JPEG — fall back
    // to checking the file extension before rejecting it outright.
    const typeOk = ALLOWED_TYPES.includes(candidate.type) || (candidate.type === "" && ALLOWED_EXTENSIONS.includes(ext));
    if (!typeOk) {
      setFileError("Use a JPEG, PNG, or WebP image.");
      return;
    }

    if (candidate.size > MAX_IMAGE_MB * 1024 * 1024) {
      setFileError(`Image is too large (${(candidate.size / (1024 * 1024)).toFixed(1)}MB). Max size is ${MAX_IMAGE_MB}MB.`);
      return;
    }

    setFileError(null);
    setFile(candidate);
    setPreview((old) => {
      if (old) URL.revokeObjectURL(old);
      return URL.createObjectURL(candidate);
    });
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (disabled || justSubmitted) return; // Case: closes the double-submit race window described above

    if (mode === "text") {
      const trimmed = ingredientsText.trim();
      if (trimmed.length < 3 || !hasRealContent(trimmed)) return;
      setJustSubmitted(true);
      onSubmitText(trimmed, productName.trim());
    } else if (mode === "image") {
      if (!file) return;
      setJustSubmitted(true);
      onSubmitImage(file, productName.trim());
    } else {
      const trimmed = productName.trim();
      if (trimmed.length < 2 || !hasRealContent(trimmed)) return;
      setJustSubmitted(true);
      onSubmitProductName(trimmed);
    }
  }

  const canSubmit =
    mode === "text"
      ? ingredientsText.trim().length >= 3 && hasRealContent(ingredientsText)
      : mode === "image"
      ? !!file && !fileError
      : productName.trim().length >= 2 && hasRealContent(productName);

  const isBusy = disabled || justSubmitted;

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className="flex gap-1 rounded-lg border border-line bg-surface p-1">
        {(["name", "image", "text"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            disabled={isBusy}
            className={`flex-1 rounded-md py-2 text-xs font-medium transition-colors sm:text-sm disabled:cursor-not-allowed disabled:opacity-60 ${
              mode === m ? "bg-ink text-paper" : "text-ink-muted hover:text-ink"
            }`}
          >
            {m === "text" ? "Paste ingredients" : m === "image" ? "Upload a photo" : "Search by name"}
          </button>
        ))}
      </div>

      {mode === "name" ? (
        <div>
          <label htmlFor="product_name_search" className="mb-1.5 block text-xs font-medium text-ink-muted">
            Product name or page link
          </label>
          <input
            id="product_name_search"
            type="text"
            value={productName}
            onChange={(e) => setProductName(e.target.value.slice(0, MAX_PRODUCT_NAME_LENGTH))}
            maxLength={MAX_PRODUCT_NAME_LENGTH}
            placeholder="e.g. Lakme 9to5 Hya Beach Edit Lipstick — or paste a product page URL"
            className="w-full rounded-lg border border-line bg-surface px-3 py-2.5 text-sm text-ink placeholder:text-ink-faint focus:border-primary"
          />
          <p className="mt-1 text-xs text-ink-faint">
            We&apos;ll search the web for this product&apos;s ingredients list — or, for the most
            reliable result, paste a direct link to the product page. If we can&apos;t find one,
            try pasting ingredients or uploading a photo instead.
          </p>
        </div>
      ) : (
        <div>
          <label htmlFor="product_name" className="mb-1.5 block text-xs font-medium text-ink-muted">
            Product name <span className="text-ink-faint">(optional)</span>
          </label>
          <input
            id="product_name"
            type="text"
            value={productName}
            onChange={(e) => setProductName(e.target.value.slice(0, MAX_PRODUCT_NAME_LENGTH))}
            maxLength={MAX_PRODUCT_NAME_LENGTH}
            placeholder="e.g. CeraVe Moisturizing Cream"
            className="w-full rounded-lg border border-line bg-surface px-3 py-2.5 text-sm text-ink placeholder:text-ink-faint focus:border-primary"
          />
        </div>
      )}

      {mode === "text" && (
        <div>
          <label htmlFor="ingredients_text" className="mb-1.5 block text-xs font-medium text-ink-muted">
            Ingredients list
          </label>
          <textarea
            id="ingredients_text"
            value={ingredientsText}
            onChange={(e) => setIngredientsText(e.target.value.slice(0, MAX_TEXT_LENGTH))}
            maxLength={MAX_TEXT_LENGTH}
            rows={6}
            placeholder="Water, Sodium Lauryl Sulfate, Parabens, Fragrance..."
            className="w-full resize-none rounded-lg border border-line bg-surface px-3 py-2.5 font-mono text-sm text-ink placeholder:font-body placeholder:text-ink-faint focus:border-primary"
          />
          <div className="mt-1 flex items-center justify-between">
            <p className="text-xs text-ink-faint">
              Separate ingredients with commas, exactly as printed on the label.
            </p>
            {ingredientsText.length > MAX_TEXT_LENGTH * 0.9 && (
              <p className="shrink-0 pl-2 text-xs text-caution">
                {ingredientsText.length}/{MAX_TEXT_LENGTH}
              </p>
            )}
          </div>
        </div>
      )}

      {mode === "image" && (
        <div>
          <label className="mb-1.5 block text-xs font-medium text-ink-muted">Label photo</label>
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              handleFile(e.dataTransfer.files?.[0]);
            }}
            onClick={() => inputRef.current?.click()}
            className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-line bg-surface px-4 py-8 text-center hover:border-primary"
          >
            {preview ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={preview} alt="Label preview" className="max-h-40 rounded-md object-contain" />
            ) : (
              <>
                <svg viewBox="0 0 24 24" fill="none" className="h-7 w-7 text-ink-faint" aria-hidden="true">
                  <path
                    d="M12 16V4m0 0 4 4m-4-4-4 4M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"
                    stroke="currentColor"
                    strokeWidth={1.6}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                <p className="text-sm text-ink-muted">Drag a photo here, or click to choose one</p>
                <p className="text-xs text-ink-faint">JPEG, PNG, or WebP · up to {MAX_IMAGE_MB}MB</p>
              </>
            )}
            <input
              ref={inputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(e) => handleFile(e.target.files?.[0])}
              className="hidden"
            />
          </div>
          {fileError && <p className="mt-1.5 text-xs text-danger">{fileError}</p>}
        </div>
      )}

      <button
        type="submit"
        disabled={!canSubmit || isBusy}
        className="w-full rounded-lg bg-primary py-3 text-sm font-medium text-white transition-colors hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-40"
      >
        {mode === "name" ? "Search & scan" : "Scan ingredients"}
      </button>
    </form>
  );
}
