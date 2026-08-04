"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  CaretLeft,
  CheckCircle,
  MagnifyingGlass,
  Plus,
  Star,
} from "@phosphor-icons/react/dist/ssr";

import { Button } from "@/components/ui/Button";

type Product = { id: string; canonical_name: string | null; category: string | null };
type Verdict = "yes_absolutely" | "it_depends" | "hard_pass";

const VERDICTS: { value: Verdict; label: string; ring: string }[] = [
  { value: "yes_absolutely", label: "Yes, absolutely", ring: "var(--accent-success)" },
  { value: "it_depends", label: "It depends", ring: "var(--accent-star)" },
  { value: "hard_pass", label: "Hard pass", ring: "var(--accent-danger)" },
];

const lines = (s: string) =>
  s.split("\n").map((x) => x.trim()).filter(Boolean).slice(0, 10);

export function WriteReviewForm() {
  const [step, setStep] = useState<"product" | "details" | "done">("product");
  const [product, setProduct] = useState<Product | null>(null);

  return (
    <div className="mx-auto w-full max-w-[42rem] px-6 py-8 lg:py-10">
      {step === "product" && (
        <ProductStep
          onPick={(p) => {
            setProduct(p);
            setStep("details");
          }}
        />
      )}
      {step === "details" && product && (
        <DetailsStep
          product={product}
          onBack={() => setStep("product")}
          onDone={() => setStep("done")}
        />
      )}
      {step === "done" && <DoneStep />}
    </div>
  );
}

function ProductStep({ onPick }: { onPick: (p: Product) => void }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Product[]>([]);
  const [busy, setBusy] = useState(false);
  const [creating, setCreating] = useState(false);

  const query = q.trim();
  const searching = query.length >= 2;

  useEffect(() => {
    if (!searching) return;
    const t = setTimeout(async () => {
      setBusy(true);
      try {
        const res = await fetch(
          `/api/bff/api/v1/products?q=${encodeURIComponent(query)}&limit=8`,
        );
        setResults(res.ok ? await res.json() : []);
      } catch {
        setResults([]);
      } finally {
        setBusy(false);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [query, searching]);

  // Derived, not stored: results from a previous query must not survive into a
  // query that no longer qualifies. Clearing via setState inside the effect body
  // would trigger a cascading render (react-hooks/set-state-in-effect).
  const visibleResults = searching ? results : [];

  async function createAndPick() {
    if (!q.trim() || creating) return;
    setCreating(true);
    try {
      const res = await fetch("/api/bff/api/v1/products", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name: q.trim() }),
      });
      if (res.ok) onPick(await res.json());
    } finally {
      setCreating(false);
    }
  }

  return (
    <div>
      <p className="text-[13px] text-[var(--text-secondary)]">Let&rsquo;s get started!</p>
      <h1 className="mt-1 text-[26px] font-bold text-[var(--accent-primary)]">
        What did you buy?
      </h1>
      <p className="mt-1 text-[14px] text-[var(--text-secondary)]">
        Find the product. No need for the exact model — just type what you know.
      </p>

      <div className="relative mt-6">
        <MagnifyingGlass
          size={20}
          className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
        />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="e.g. Jisulife Fan Life9"
          className="h-12 w-full rounded-[var(--radius-pill)] bg-[var(--surface-card)] pl-11 pr-4 text-[14px] text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)] outline-none placeholder:text-[var(--text-muted)] focus-visible:shadow-[0_0_0_2px_var(--accent-primary)]"
        />
      </div>

      <ul className="mt-4 flex flex-col gap-2">
        {visibleResults.map((p) => (
          <li key={p.id}>
            <button
              type="button"
              onClick={() => onPick(p)}
              className="flex w-full items-center gap-3 rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-3 text-left shadow-[var(--shadow-hairline-inset)] hover:outline hover:outline-1 hover:outline-[var(--accent-primary)]"
            >
              <span className="h-9 w-9 shrink-0 rounded-[8px] bg-[var(--base-gray-200)]" />
              <span className="text-[14px] font-medium text-[var(--text-primary)]">
                {p.canonical_name ?? "Unnamed product"}
              </span>
              {p.category ? (
                <span className="ml-auto text-[12px] capitalize text-[var(--text-muted)]">
                  {p.category}
                </span>
              ) : null}
            </button>
          </li>
        ))}
        {searching && !busy ? (
          <li>
            <button
              type="button"
              onClick={createAndPick}
              disabled={creating}
              className="flex w-full items-center gap-3 rounded-[var(--radius-sm)] border border-dashed border-[var(--line-hairline-30)] p-3 text-left hover:border-[var(--accent-primary)] disabled:opacity-60"
            >
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-[8px] bg-[color-mix(in_srgb,var(--accent-primary)_12%,transparent)] text-[var(--accent-primary)]">
                <Plus size={18} weight="bold" />
              </span>
              <span className="text-[14px] text-[var(--text-primary)]">
                Add &ldquo;<span className="font-semibold">{q.trim()}</span>&rdquo; as a new product
              </span>
            </button>
          </li>
        ) : null}
      </ul>
    </div>
  );
}

function DetailsStep({
  product,
  onBack,
  onDone,
}: {
  product: Product;
  onBack: () => void;
  onDone: () => void;
}) {
  const [title, setTitle] = useState("");
  const [discussion, setDiscussion] = useState("");
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [rating, setRating] = useState(0);
  const [target, setTarget] = useState("");
  const [anti, setAnti] = useState("");
  const [pros, setPros] = useState("");
  const [cons, setCons] = useState("");
  const [price, setPrice] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const ready = title.trim() && discussion.trim() && verdict && rating > 0;

  async function submit() {
    if (!ready || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/bff/api/v1/reviews", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          product_id: product.id,
          title: title.trim(),
          discussion: discussion.trim(),
          verdict,
          star_rating: rating,
          target_audience: target.trim() || null,
          anti_target_audience: anti.trim() || null,
          pros: lines(pros),
          cons: lines(cons),
          price_paid: price.trim() ? Number(price) : null,
        }),
      });
      if (!res.ok) {
        const p = (await res.json().catch(() => ({}))) as { detail?: string };
        setError(p.detail ?? "Something went wrong submitting your review.");
        return;
      }
      onDone();
    } catch {
      setError("Couldn't reach the server. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <button
        type="button"
        onClick={onBack}
        className="inline-flex items-center gap-1 text-[13px] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
      >
        <CaretLeft size={16} /> Change product
      </button>
      <h1 className="mt-4 text-[24px] font-bold text-[var(--text-primary)]">
        Reviewing{" "}
        <span className="text-[var(--accent-primary)]">
          {product.canonical_name ?? "your product"}
        </span>
      </h1>

      <div className="mt-6 flex flex-col gap-5">
        <Field label="Review title">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={200}
            placeholder="Worth the money, or just overhyped?"
            className={inputCls}
          />
        </Field>

        <Field label="Your verdict">
          <div className="flex flex-wrap gap-2">
            {VERDICTS.map((v) => (
              <button
                key={v.value}
                type="button"
                onClick={() => setVerdict(v.value)}
                className="rounded-[var(--radius-pill)] px-4 py-2 text-[13px] font-semibold transition-shadow"
                style={
                  verdict === v.value
                    ? { boxShadow: `inset 0 0 0 2px ${v.ring}`, color: v.ring }
                    : { boxShadow: "inset 0 0 0 1px var(--line-hairline-30)", color: "var(--text-secondary)" }
                }
              >
                {v.label}
              </button>
            ))}
          </div>
        </Field>

        <Field label="Star rating">
          <div className="flex gap-1">
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                key={n}
                type="button"
                onClick={() => setRating(n)}
                aria-label={`${n} star${n > 1 ? "s" : ""}`}
              >
                <Star
                  size={28}
                  weight={n <= rating ? "fill" : "regular"}
                  className={n <= rating ? "text-[var(--accent-star)]" : "text-[var(--base-gray-300)]"}
                />
              </button>
            ))}
          </div>
        </Field>

        <Field label="The review">
          <textarea
            value={discussion}
            onChange={(e) => setDiscussion(e.target.value)}
            rows={5}
            placeholder="Tell the community what your experience was really like."
            className={`${inputCls} resize-y py-3`}
          />
        </Field>

        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Pros (one per line)">
            <textarea value={pros} onChange={(e) => setPros(e.target.value)} rows={4} className={`${inputCls} resize-y py-3`} />
          </Field>
          <Field label="Cons (one per line)">
            <textarea value={cons} onChange={(e) => setCons(e.target.value)} rows={4} className={`${inputCls} resize-y py-3`} />
          </Field>
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Best for (optional)">
            <input value={target} onChange={(e) => setTarget(e.target.value)} className={inputCls} placeholder="Who should buy this?" />
          </Field>
          <Field label="Not for (optional)">
            <input value={anti} onChange={(e) => setAnti(e.target.value)} className={inputCls} placeholder="Who should skip it?" />
          </Field>
        </div>

        <Field label="Price paid (optional, ₱)">
          <input
            value={price}
            onChange={(e) => setPrice(e.target.value.replace(/[^0-9.]/g, ""))}
            inputMode="decimal"
            className={inputCls}
            placeholder="899"
          />
        </Field>

        {error ? (
          <p role="alert" className="rounded-[var(--radius-sm)] bg-[color-mix(in_srgb,var(--accent-danger)_10%,transparent)] px-4 py-3 text-[13px] text-[var(--accent-danger)]">
            {error}
          </p>
        ) : null}

        <div className="flex items-center gap-3">
          <Button type="button" onClick={submit} disabled={!ready || busy}>
            {busy ? "Submitting…" : "Submit for review"}
          </Button>
          <p className="text-[12px] text-[var(--text-muted)]">
            A moderator checks every review before it goes live.
          </p>
        </div>
      </div>
    </div>
  );
}

function DoneStep() {
  return (
    <div className="flex flex-col items-center py-16 text-center">
      <CheckCircle size={56} weight="fill" className="text-[var(--accent-success)]" />
      <h1 className="mt-5 text-[24px] font-bold text-[var(--text-primary)]">
        Your review is in!
      </h1>
      <p className="mt-2 max-w-[26rem] text-[14px] text-[var(--text-secondary)]">
        A moderator will check it shortly. Once approved, it goes live — and if it
        earns an affiliate link, you start earning from it.
      </p>
      <div className="mt-8 flex gap-3">
        <Link href="/" className="contents">
          <Button variant="secondary" size="sm">Back home</Button>
        </Link>
        <Link href="/reviews/new" className="contents">
          <Button size="sm">Write another</Button>
        </Link>
      </div>
    </div>
  );
}

const inputCls =
  "w-full rounded-[var(--radius-sm)] bg-[var(--surface-card)] px-4 py-2.5 text-[14px] text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)] outline-none placeholder:text-[var(--text-muted)] focus-visible:shadow-[0_0_0_2px_var(--accent-primary)]";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-[13px] font-medium text-[var(--text-primary)]">{label}</span>
      {children}
    </label>
  );
}
