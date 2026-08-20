"use client";

import { useState } from "react";
import { ArrowSquareOut, LinkSimple, Receipt, Warning } from "@phosphor-icons/react/dist/ssr";

import { Button } from "@/components/ui/Button";
import type { QueueItem } from "@/lib/moderation";

const VERDICT_LABEL: Record<string, string> = {
  yes_absolutely: "Yes, absolutely",
  it_depends: "It depends",
  hard_pass: "Hard pass",
};

export function ModerationQueue({ initial }: { initial: QueueItem[] }) {
  const [items, setItems] = useState(initial);

  if (items.length === 0) {
    return (
      <div className="rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-10 text-center shadow-[var(--shadow-hairline-inset)]">
        <p className="text-[15px] font-semibold text-[var(--text-primary)]">
          Queue is clear
        </p>
        <p className="mt-1 text-[14px] text-[var(--text-secondary)]">
          No reviews are waiting for moderation right now.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {items.map((item) => (
        <ModerationCard
          key={item.review.id}
          item={item}
          onResolve={() =>
            setItems((cur) => cur.filter((i) => i.review.id !== item.review.id))
          }
        />
      ))}
    </div>
  );
}

function ModerationCard({
  item,
  onResolve,
}: {
  item: QueueItem;
  onResolve: () => void;
}) {
  const { review, product, author, signals } = item;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attaching, setAttaching] = useState(false);
  const [url, setUrl] = useState("");
  const [receiptBusy, setReceiptBusy] = useState(false);
  const [platform, setPlatform] = useState(item.suggested_platform ?? "shopee");

  const flags = [
    signals.velocity && "Upvote velocity",
    signals.collusion && "Voter collusion",
    signals.duplicate_content && "Duplicate content",
  ].filter(Boolean) as string[];

  async function act(
    method: "POST" | "DELETE",
    path: string,
    body?: unknown,
  ): Promise<boolean> {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/bff/api/v1/admin/${path}`, {
        method,
        headers: body ? { "content-type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!res.ok) {
        const p = (await res.json().catch(() => ({}))) as { detail?: string };
        setError(p.detail ?? "Action failed.");
        return false;
      }
      return true;
    } catch {
      setError("Couldn't reach the server.");
      return false;
    } finally {
      setBusy(false);
    }
  }

  /** Fetch a short-lived signed URL and open it. Deliberately not rendered as
   *  an <img src>: the URL is a bearer credential, and putting it in the DOM
   *  leaves it in the page source and in any screenshot of this queue. It is
   *  requested at the moment of use and never stored. */
  async function openReceipt() {
    setReceiptBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/bff/api/v1/reviews/${review.id}/receipt`);
      if (!res.ok) {
        setError("Couldn't open the proof of purchase.");
        return;
      }
      const { url: signed } = (await res.json()) as { url: string };
      window.open(signed, "_blank", "noopener,noreferrer");
    } catch {
      setError("Couldn't reach the server.");
    } finally {
      setReceiptBusy(false);
    }
  }

  async function publish() {
    if (await act("POST", `reviews/${review.id}/publish`)) onResolve();
  }
  async function reject() {
    const reason = window.prompt("Reason for rejection (shown to the author):");
    if (!reason) return;
    if (await act("POST", `reviews/${review.id}/reject`, { reason })) onResolve();
  }
  async function attach() {
    if (!url.trim()) return;
    const ok = await act("POST", `reviews/${review.id}/referral-link`, {
      url: url.trim(),
      platform,
      sub_id: item.suggested_sub_id,
    });
    if (ok) onResolve();
  }

  return (
    <article className="rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-card)]">
      <div className="flex flex-wrap items-center gap-2 text-[12px] text-[var(--text-muted)]">
        <span className="font-medium text-[var(--text-secondary)]">
          {product.canonical_name ?? "Unnamed product"}
        </span>
        {product.source_url ? (
          <a
            href={product.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-[var(--accent-primary)] hover:underline"
          >
            source <ArrowSquareOut size={12} />
          </a>
        ) : null}
        {review.has_receipt ? (
          <button
            type="button"
            onClick={() => void openReceipt()}
            disabled={receiptBusy}
            // -my/py so the 12px label still presents a 24px hit area
            // (WCAG 2.5.8) without changing how the row looks.
            className="-my-1.5 inline-flex items-center gap-1 py-1.5 text-[var(--accent-primary)] hover:underline disabled:opacity-60"
          >
            <Receipt size={12} />
            {receiptBusy ? "opening…" : "proof of purchase"}
          </button>
        ) : null}
        <span className="ml-auto">
          {review.verification_status === "verified" ? "✓ verified" : "unverified"}
        </span>
      </div>

      <h3 className="mt-2 text-[16px] font-semibold text-[var(--text-primary)]">
        {review.title}
      </h3>
      <p className="mt-1 text-[13px] text-[var(--text-secondary)]">
        {VERDICT_LABEL[review.verdict]} · {review.star_rating}★ · by{" "}
        {author?.display_name ?? "unknown"} (Stage {author?.trust_stage ?? 0})
      </p>
      <p className="mt-3 line-clamp-3 text-[14px] text-[var(--text-secondary)]">
        {review.discussion}
      </p>

      {flags.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {flags.map((f) => (
            <span
              key={f}
              className="inline-flex items-center gap-1 rounded-[var(--radius-md)] bg-[color-mix(in_srgb,var(--accent-star)_18%,transparent)] px-2.5 py-1 text-[11px] font-medium text-[var(--base-ink-700)]"
            >
              <Warning size={12} weight="fill" /> {f}
            </span>
          ))}
        </div>
      ) : null}

      {attaching ? (
        <div className="mt-4 flex flex-col gap-2 rounded-[var(--radius-sm)] bg-[var(--surface-app)] p-3">
          <p className="text-[12px] text-[var(--text-secondary)]">
            Sub-ID to paste into the affiliate dashboard:{" "}
            <code className="font-semibold text-[var(--text-primary)]">
              {item.suggested_sub_id}
            </code>
          </p>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="Paste the affiliate link…"
              className="h-10 flex-1 rounded-[var(--radius-pill)] bg-[var(--surface-card)] px-4 text-[13px] text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)] outline-none focus-visible:shadow-[0_0_0_2px_var(--accent-primary)]"
            />
            <select
              value={platform}
              onChange={(e) => setPlatform(e.target.value)}
              className="h-10 rounded-[var(--radius-pill)] bg-[var(--surface-card)] px-3 text-[13px] text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)]"
            >
              {["shopee", "lazada", "amazon", "other"].map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
            <Button size="sm" onClick={attach} disabled={busy || !url.trim()}>
              Monetize &amp; publish
            </Button>
          </div>
        </div>
      ) : null}

      {error ? (
        <p role="alert" className="mt-3 text-[12px] text-[var(--accent-danger)]">
          {error}
        </p>
      ) : null}

      <div className="mt-4 flex flex-wrap gap-2 border-t border-[var(--border-subtle)] pt-4">
        <Button
          size="sm"
          onClick={() => setAttaching((v) => !v)}
          icon={<LinkSimple size={14} />}
        >
          {attaching ? "Cancel link" : "Attach affiliate link"}
        </Button>
        <Button variant="secondary" size="sm" onClick={publish} disabled={busy}>
          Publish (no link)
        </Button>
        <Button variant="secondary" size="sm" onClick={reject} disabled={busy}>
          Reject
        </Button>
      </div>
    </article>
  );
}

export default ModerationQueue;
