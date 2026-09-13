"use client";

import { useRef, useState } from "react";
import { Image as ImageIcon, Trash } from "@phosphor-icons/react/dist/ssr";

import { prepareImageForUpload } from "@/lib/image";

/**
 * KEPT AND INTENTIONALLY UNMOUNTED.
 *
 * The reviewer pack's step 6 has exactly one upload — the product photo — and
 * assigns verification to it, so the composer no longer renders this field.
 * It is not dead code to delete: the backend's earn_eligible gate reads
 * `receipt_key` and nothing else, so removing the only way to supply one is a
 * product decision for the owner, not a side effect of matching a frame.
 *
 * Mounting it again is a one-line change wherever proof of purchase belongs.
 */

/**
 * Proof of purchase — private storage, deliberately not a PhotoField.
 *
 * Three differences from the public photo field, all of them the point:
 *  - it posts to /reviews/receipt, so the *server* picks the private bucket;
 *    the client never names a destination
 *  - it stores an opaque object key, not a URL
 *  - the preview URL is signed, short-lived, and held only in component state.
 *    Resuming a saved draft therefore shows "attached" rather than the image:
 *    persisting the signed URL to survive a reload is exactly the mistake this
 *    whole change exists to undo.
 */
export function ReceiptField({
  value,
  onChange,
}: {
  value: string | null;
  onChange: (key: string | null) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<string | null>(null);

  async function pick(file: File) {
    setBusy(true);
    setError(null);
    try {
      // Shrink before sending: the platform refuses a body over ~4.5MB with a
      // bare 413, and a phone photo of a receipt is routinely larger. Kept at a
      // higher resolution than the proof photo because a moderator has to read
      // the small print on it.
      const prepared = await prepareImageForUpload(file, "document");
      if (prepared.error) {
        setError(prepared.error);
        return;
      }
      const body = new FormData();
      body.append("file", prepared.file);
      const res = await fetch("/api/bff/api/v1/reviews/receipt", {
        method: "POST",
        body,
      });
      if (!res.ok) {
        const p = (await res.json().catch(() => ({}))) as { detail?: string };
        setError(p.detail ?? "That image couldn't be uploaded.");
        return;
      }
      const { key, preview_url } = (await res.json()) as {
        key: string;
        preview_url: string;
      };
      onChange(key);
      setPreview(preview_url);
    } catch {
      setError("Couldn't reach the server.");
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[13px] font-medium text-[var(--text-primary)]">
        Proof of purchase
      </span>
      <span className="text-[12px] text-[var(--text-secondary)]">
        A receipt, order screenshot, or the confirmation email. Only you and the
        moderators reviewing it can ever open this — it is never shown on your
        published review.
      </span>

      {value ? (
        <div className="mt-2 flex items-start gap-3">
          {preview ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={preview}
              alt="Proof of purchase preview"
              className="h-28 w-28 rounded-[var(--radius-sm)] object-cover shadow-[var(--shadow-hairline-inset)]"
            />
          ) : (
            <div className="grid h-28 w-28 place-items-center rounded-[var(--radius-sm)] text-center text-[12px] text-[var(--text-secondary)] shadow-[var(--shadow-hairline-inset)]">
              Attached
            </div>
          )}
          <button
            type="button"
            onClick={() => {
              onChange(null);
              setPreview(null);
            }}
            className="inline-flex items-center gap-1.5 rounded-[var(--radius-pill)] px-3 py-2 text-[13px] text-[var(--accent-danger)] hover:bg-[color-mix(in_srgb,var(--accent-danger)_10%,transparent)]"
          >
            <Trash size={16} /> Remove
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => input.current?.click()}
          disabled={busy}
          className="mt-2 inline-flex items-center gap-2 self-start rounded-[var(--radius-sm)] border border-dashed border-[var(--line-hairline-30)] px-4 py-3 text-[13px] text-[var(--text-secondary)] hover:border-[var(--accent-primary)] hover:text-[var(--text-primary)] disabled:opacity-60"
        >
          <ImageIcon size={18} />
          {busy ? "Uploading…" : "Choose an image"}
        </button>
      )}

      <input
        ref={input}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void pick(file);
        }}
      />
      {error ? (
        <p className="text-[12px] text-[var(--accent-danger)]">{error}</p>
      ) : null}
    </div>
  );
}

export default ReceiptField;
