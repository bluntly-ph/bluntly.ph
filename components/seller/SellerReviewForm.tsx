"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Star } from "@phosphor-icons/react/dist/ssr";

import { Button } from "@/components/ui/Button";

/** Rate a seller on the four dimensions (POST /sellers/{id}/reviews). */
export function SellerReviewForm({
  sellerId,
  canReview,
}: {
  sellerId: string;
  canReview: boolean;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [accuracy, setAccuracy] = useState<boolean | null>(null);
  const [complete, setComplete] = useState<boolean | null>(null);
  const [recommend, setRecommend] = useState<boolean | null>(null);
  const [service, setService] = useState(0);
  const [packaging, setPackaging] = useState(0);
  const [overall, setOverall] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ready =
    accuracy !== null &&
    complete !== null &&
    recommend !== null &&
    service > 0 &&
    packaging > 0 &&
    overall > 0;

  if (!open) {
    return (
      <Button
        size="sm"
        onClick={() => (canReview ? setOpen(true) : router.push("/login"))}
      >
        Rate this seller
      </Button>
    );
  }

  async function submit() {
    if (!ready || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/bff/api/v1/sellers/${sellerId}/reviews`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          accuracy,
          order_completeness: complete,
          customer_service: service,
          packaging_quality: packaging,
          overall_rating: overall,
          would_recommend: recommend,
        }),
      });
      if (!res.ok) {
        const p = (await res.json().catch(() => ({}))) as { detail?: string };
        setError(p.detail ?? "Couldn't submit that review.");
        return;
      }
      setOpen(false);
      router.refresh();
    } catch {
      setError("Couldn't reach the server.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-card)]">
      <h3 className="text-[15px] font-semibold text-[var(--text-primary)]">Rate this seller</h3>
      <div className="mt-4 flex flex-col gap-4">
        <YesNo label="Product matched the listing?" value={accuracy} onChange={setAccuracy} />
        <YesNo label="Order arrived complete?" value={complete} onChange={setComplete} />
        <Stars label="Customer service" value={service} onChange={setService} />
        <Stars label="Packaging quality" value={packaging} onChange={setPackaging} />
        <Stars label="Overall" value={overall} onChange={setOverall} />
        <YesNo label="Would you recommend them?" value={recommend} onChange={setRecommend} />
        {error ? <p role="alert" className="text-[12px] text-[var(--accent-danger)]">{error}</p> : null}
        <div className="flex gap-2">
          <Button size="sm" onClick={submit} disabled={!ready || busy}>
            {busy ? "Submitting…" : "Submit rating"}
          </Button>
          <Button variant="secondary" size="sm" onClick={() => setOpen(false)}>
            Cancel
          </Button>
        </div>
      </div>
    </div>
  );
}

function YesNo({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean | null;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-[13px] text-[var(--text-primary)]">{label}</span>
      <div className="flex gap-2">
        {[true, false].map((v) => (
          <button
            key={String(v)}
            type="button"
            onClick={() => onChange(v)}
            className={`rounded-[var(--radius-pill)] px-4 py-1.5 text-[13px] font-medium ${
              value === v
                ? "bg-[var(--accent-primary)] text-white"
                : "bg-[var(--surface-app)] text-[var(--text-secondary)]"
            }`}
          >
            {v ? "Yes" : "No"}
          </button>
        ))}
      </div>
    </div>
  );
}

function Stars({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-[13px] text-[var(--text-primary)]">{label}</span>
      <div className="flex gap-1">
        {[1, 2, 3, 4, 5].map((n) => (
          <button key={n} type="button" onClick={() => onChange(n)} aria-label={`${n}`}>
            <Star
              size={22}
              weight={n <= value ? "fill" : "regular"}
              className={n <= value ? "text-[var(--accent-star)]" : "text-[var(--base-gray-300)]"}
            />
          </button>
        ))}
      </div>
    </div>
  );
}

export default SellerReviewForm;
