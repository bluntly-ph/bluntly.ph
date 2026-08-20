/**
 * Shrink a photo in the browser before it is uploaded.
 *
 * Measured against production on 2026-08-20: the platform refuses a request
 * body somewhere between 3.0 MB and 4.4 MB with a bare `413`, while the API
 * advertises an 8 MB cap it can therefore never receive. A phone photo is
 * routinely 4–8 MB, and FR-3 makes that photo mandatory at submission — so the
 * one upload every reviewer must complete was the one most likely to fail, and
 * to fail with a platform error page rather than anything the form could
 * explain.
 *
 * Raising the platform limit is not available, and lowering the API cap only
 * moves the failure earlier. Resizing removes it: a 4032×3024 phone photo comes
 * out around 300 KB at 1600 px, which is more resolution than any layout here
 * displays.
 *
 * Deliberately does not fail closed. If the browser cannot decode the file —
 * HEIC from an iPhone is the common case, since Safari decodes it but other
 * browsers do not — the original is returned and the server decides. A reviewer
 * whose photo we cannot read in JavaScript should still get the server's
 * message, not ours.
 */

/** Longest edge, in pixels, after resizing. */
const MAX_EDGE = 1600;

/**
 * Receipts are read by a moderator, and sometimes squinted at — a receipt is
 * mostly small text, which is exactly what aggressive resizing destroys.
 */
const MAX_EDGE_DOCUMENT = 2200;

/** Below this, resizing costs quality and saves nothing worth having. */
const SKIP_BELOW_BYTES = 512 * 1024;

/** Comfortably under the platform's limit, leaving room for multipart overhead. */
export const MAX_UPLOAD_BYTES = 4 * 1024 * 1024;

export type PrepareKind = "photo" | "document";

export type PrepareResult = {
  file: File;
  /** True when the returned file is not the one that went in. */
  resized: boolean;
  /** Set when the file cannot be uploaded at all, already human-readable. */
  error?: string;
};

function isImage(file: File): boolean {
  // HEIC often arrives with an empty type, so an empty type is not a rejection.
  return file.type === "" || file.type.startsWith("image/");
}

async function decode(file: File): Promise<ImageBitmap | null> {
  try {
    return await createImageBitmap(file);
  } catch {
    return null;
  }
}

function toBlob(canvas: HTMLCanvasElement, quality: number): Promise<Blob | null> {
  return new Promise((resolve) =>
    canvas.toBlob((b) => resolve(b), "image/jpeg", quality),
  );
}

/**
 * Returns a file small enough to upload, the original when that is already
 * true, or an error the caller can show as-is.
 */
export async function prepareImageForUpload(
  file: File,
  kind: PrepareKind = "photo",
): Promise<PrepareResult> {
  if (!isImage(file)) {
    return { file, resized: false, error: "That file isn't an image." };
  }
  if (file.size <= SKIP_BELOW_BYTES) return { file, resized: false };

  const bitmap = await decode(file);
  if (!bitmap) {
    // Undecodable here; small enough to try anyway, or too big to bother.
    return file.size <= MAX_UPLOAD_BYTES
      ? { file, resized: false }
      : {
          file,
          resized: false,
          error:
            "That image is too large to upload, and this browser can't resize " +
            "it. Try saving it as a JPEG first.",
        };
  }

  const maxEdge = kind === "document" ? MAX_EDGE_DOCUMENT : MAX_EDGE;
  const scale = Math.min(1, maxEdge / Math.max(bitmap.width, bitmap.height));

  // Already small enough in both senses: don't re-encode and lose quality.
  if (scale === 1 && file.size <= MAX_UPLOAD_BYTES) {
    bitmap.close();
    return { file, resized: false };
  }

  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    bitmap.close();
    return { file, resized: false };
  }
  ctx.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  bitmap.close();

  // Step the quality down rather than guessing once. Three attempts is enough
  // to bring anything a phone produces under the limit, and each is cheap.
  for (const quality of [0.85, 0.7, 0.55]) {
    const blob = await toBlob(canvas, quality);
    if (!blob) break;
    if (blob.size <= MAX_UPLOAD_BYTES) {
      const name = file.name.replace(/\.[^.]+$/, "") + ".jpg";
      return {
        file: new File([blob], name, { type: "image/jpeg" }),
        resized: true,
      };
    }
  }

  return {
    file,
    resized: false,
    error: "That image is too large, even after resizing. Try a smaller photo.",
  };
}

/** Human-readable size, for telling someone what went wrong. */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
