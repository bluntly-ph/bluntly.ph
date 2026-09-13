"use client";

import Link from "next/link";
import { useId, useState } from "react";

import { Button } from "@/components/ui/Button";

/**
 * "Do you run this store?" — a claim REQUEST, never ownership.
 *
 * FR-4 limits seller verification to a moderator cross-checking the store name
 * against the public listing, so submitting here changes nothing on the page:
 * the claim waits in the moderator queue, and the profile reads "Claimed" only
 * after a moderator approves it. The copy says exactly that, so a claimant is
 * not left thinking the badge is broken.
 */
export function ClaimSellerForm({ sellerId, signedIn }: { sellerId: string; signedIn: boolean }) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [evidence, setEvidence] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!evidence.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/bff/api/v1/sellers/${sellerId}/claims`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ evidence: evidence.trim() }),
      });
      if (!res.ok) {
        const p = (await res.json().catch(() => ({}))) as { detail?: string };
        setError(p.detail ?? "Couldn't send your claim.");
        return;
      }
      setSent(true);
    } catch {
      setError("Couldn't reach the server.");
    } finally {
      setBusy(false);
    }
  }

  const pill =
    "mt-4 inline-flex h-9 cursor-pointer items-center rounded-[var(--radius-pill)] border border-[var(--base-gray-600)] px-4 text-[14px] text-[var(--text-primary)] no-underline hover:border-[var(--accent-primary)] hover:text-[var(--accent-primary)]";

  if (!signedIn) {
    return (
      <Link href="/login" className={pill}>
        Log in to claim this store
      </Link>
    );
  }

  if (sent) {
    return (
      <p
        role="status"
        className="mt-4 rounded-[var(--radius-sm)] bg-[color-mix(in_srgb,var(--accent-trust)_12%,transparent)] px-4 py-3 text-[13px] text-[var(--text-primary)]"
      >
        Your claim is in. A moderator will check it against the public listing, and this page
        will show the store as claimed only once they approve it.
      </p>
    );
  }

  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} className={pill}>
        Claim this store
      </button>
    );
  }

  return (
    <form onSubmit={submit} className="mt-4 flex flex-col gap-3">
      <label htmlFor={id} className="text-[13px] font-medium text-[var(--text-primary)]">
        How can a moderator confirm you run it?
      </label>
      <textarea
        id={id}
        value={evidence}
        onChange={(e) => setEvidence(e.target.value.slice(0, 4000))}
        rows={4}
        placeholder="For example: the store page link, and where on it your business name appears."
        className="w-full resize-y rounded-[var(--radius-sm)] bg-[var(--surface-card)] px-4 py-3 text-[14px] text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)] outline-none placeholder:text-[var(--text-muted)] focus-visible:shadow-[0_0_0_2px_var(--accent-primary)]"
      />
      <p className="text-[12px] text-[var(--text-secondary)]">
        Don&rsquo;t include ID numbers or personal documents. Moderators only compare the store
        name against the public listing.
      </p>
      {error ? (
        <p role="alert" className="text-[13px] text-[var(--accent-danger)]">
          {error}
        </p>
      ) : null}
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={!evidence.trim() || busy}>
          {busy ? "Sending…" : "Send claim"}
        </Button>
        <button
          type="button"
          onClick={() => setOpen(false)}
          className="cursor-pointer text-[14px] text-[var(--text-secondary)] underline-offset-4 hover:underline"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

export default ClaimSellerForm;
