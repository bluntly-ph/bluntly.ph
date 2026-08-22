"use client";

import Image from "next/image";
import Link from "next/link";
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import {
  CaretLeft,
  CheckCircle,
  Image as ImageIcon,
  MagnifyingGlass,
  Link as LinkIcon,
  Star,
  Trash,
} from "@phosphor-icons/react/dist/ssr";

import { Button } from "@/components/ui/Button";
import { prepareImageForUpload } from "@/lib/image";

type Product = { id: string; canonical_name: string | null; category: string | null };
type Verdict = "yes_absolutely" | "it_depends" | "hard_pass";

const VERDICTS: { value: Verdict; label: string; hint: string; ring: string }[] = [
  {
    value: "yes_absolutely",
    label: "Yes, absolutely",
    hint: "You'd tell a friend to buy it.",
    ring: "var(--accent-success)",
  },
  {
    value: "it_depends",
    label: "It depends",
    hint: "Right for some people, wrong for others.",
    ring: "var(--accent-star)",
  },
  {
    value: "hard_pass",
    label: "Hard pass",
    hint: "You'd tell a friend to save their money.",
    ring: "var(--accent-danger)",
  },
];

/** Enforced in the API too (MAX_DISCUSSION_CHARS) — BUG-022. */
const MAX_DISCUSSION = 5000;
const MAX_TITLE = 200;

const lines = (s: string) =>
  s.split("\n").map((x) => x.trim()).filter(Boolean).slice(0, 10);

/* ------------------------------------------------------------------ draft */

/**
 * The draft (BUG-024).
 *
 * Everything typed lives in one object so saving is a single write and
 * restoring is a single read. Version the key rather than migrating: a stale
 * shape from an older build should be ignored, not half-applied to a form whose
 * fields have moved.
 */
const DRAFT_KEY = "bluntly:review-draft:v1";

type Draft = {
  step: number;
  product: Product | null;
  title: string;
  discussion: string;
  verdict: Verdict | null;
  rating: number;
  pros: string;
  cons: string;
  target: string;
  anti: string;
  photoUrl: string | null;
  // The private object key from POST /reviews/receipt. Never a URL, and never
  // the signed preview URL: that is a short-lived bearer credential, and
  // localStorage would outlive it and travel with a synced browser profile.
  receiptKey: string | null;
  price: string;
  savedAt: number;
};

const EMPTY_DRAFT: Draft = {
  step: 0,
  product: null,
  title: "",
  discussion: "",
  verdict: null,
  rating: 0,
  pros: "",
  cons: "",
  target: "",
  anti: "",
  photoUrl: null,
  receiptKey: null,
  price: "",
  savedAt: 0,
};

function readDraft(): Draft | null {
  try {
    const raw = window.localStorage.getItem(DRAFT_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<Draft>;
    // A draft with nothing in it is noise — don't offer to resume it.
    if (!parsed.product && !parsed.discussion?.trim() && !parsed.title?.trim()) {
      return null;
    }
    // Drafts written before receipts moved to private storage carry a
    // `receiptUrl` pointing at an object that no longer exists publicly.
    // Drop it; the author can re-attach.
    const { ...rest } = parsed as Partial<Draft> & { receiptUrl?: unknown };
    delete (rest as { receiptUrl?: unknown }).receiptUrl;
    return { ...EMPTY_DRAFT, ...rest };
  } catch {
    return null;
  }
}

function clearDraft() {
  try {
    window.localStorage.removeItem(DRAFT_KEY);
  } catch {
    /* private mode, quota — losing a draft must never break submission */
  }
}

/**
 * Whether we are past hydration.
 *
 * The saved draft cannot be read while rendering on the server, and reading it
 * during the first client render would produce a tree that disagrees with the
 * server's. useSyncExternalStore is the sanctioned way to say "these two
 * renders legitimately differ" — and unlike setting state in an effect, it does
 * not schedule a cascading render (react-hooks/set-state-in-effect).
 */
const NO_OP_SUBSCRIBE = () => () => {};

function useHydrated(): boolean {
  return useSyncExternalStore(
    NO_OP_SUBSCRIBE,
    () => true,
    () => false,
  );
}

/* ------------------------------------------------------------------- steps */

/**
 * The seven steps from the spec, in order, after the product is chosen
 * (BUG-019). One question per screen: the whole form used to arrive at once,
 * which is why a reviewer could reach the button with the verdict unset and no
 * idea which field was missing.
 */
const STEPS = [
  "Your experience",
  "Your verdict",
  "Star rating",
  "Pros and cons",
  "Who it's not for",
  "Proof of purchase",
  "Title",
] as const;

export function WriteReviewForm() {
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [product, setProduct] = useState<Product | null>(null);
  const [phase, setPhase] = useState<"product" | "steps" | "done">("product");
  const [dismissed, setDismissed] = useState(false);

  const hydrated = useHydrated();
  // Captured once, at hydration: the autosave below rewrites the same key on
  // every keystroke, and re-reading it would keep resurrecting the banner with
  // the reviewer's own in-progress work.
  const savedDraft = useMemo(() => (hydrated ? readDraft() : null), [hydrated]);
  const resumable = dismissed ? null : savedDraft;

  // Persist on every change, but only once there is something worth keeping.
  // Writing to an external store is what effects are for; no state is set here.
  useEffect(() => {
    if (!hydrated) return;
    if (!product && !draft.discussion.trim() && !draft.title.trim()) return;
    try {
      window.localStorage.setItem(
        DRAFT_KEY,
        JSON.stringify({ ...draft, product, savedAt: Date.now() }),
      );
    } catch {
      /* see clearDraft */
    }
  }, [draft, product, hydrated]);

  const patch = useCallback(
    (changes: Partial<Draft>) => setDraft((d) => ({ ...d, ...changes })),
    [],
  );

  function resume() {
    const saved = resumable;
    if (!saved) return;
    setDraft(saved);
    setProduct(saved.product);
    setPhase(saved.product ? "steps" : "product");
    setDismissed(true);
  }

  function discard() {
    clearDraft();
    setDismissed(true);
  }

  if (phase === "done") {
    return (
      <div className="mx-auto w-full max-w-[42rem] px-6 py-8 lg:py-10">
        <DoneStep />
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-[42rem] px-6 py-8 lg:py-10">
      {resumable ? (
        <ResumeBanner draft={resumable} onResume={resume} onDiscard={discard} />
      ) : null}

      {phase === "product" ? (
        <ProductStep
          onPick={(p) => {
            setProduct(p);
            patch({ step: 0 });
            setPhase("steps");
          }}
        />
      ) : product ? (
        <StepsFlow
          product={product}
          draft={draft}
          patch={patch}
          onChangeProduct={() => setPhase("product")}
          onDone={() => {
            clearDraft();
            setPhase("done");
          }}
        />
      ) : null}
    </div>
  );
}

function ResumeBanner({
  draft,
  onResume,
  onDiscard,
}: {
  draft: Draft;
  onResume: () => void;
  onDiscard: () => void;
}) {
  const when = draft.savedAt
    ? new Date(draft.savedAt).toLocaleString("en-PH", {
        dateStyle: "medium",
        timeStyle: "short",
      })
    : null;
  return (
    <div className="mb-6 rounded-[var(--radius-sm)] bg-[color-mix(in_srgb,var(--accent-primary)_8%,transparent)] p-4">
      <p className="text-[14px] font-semibold text-[var(--text-primary)]">
        You have an unfinished review
        {draft.product?.canonical_name ? ` of ${draft.product.canonical_name}` : ""}.
      </p>
      {when ? (
        <p className="mt-1 text-[12px] text-[var(--text-secondary)]">Saved {when}.</p>
      ) : null}
      <div className="mt-3 flex gap-2">
        <Button type="button" size="sm" onClick={onResume}>
          Pick up where I left off
        </Button>
        <Button type="button" size="sm" variant="secondary" onClick={onDiscard}>
          Start fresh
        </Button>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------------- product */

function ProductStep({ onPick }: { onPick: (p: Product) => void }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Product[]>([]);
  const [busy, setBusy] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [sourceUrl, setSourceUrl] = useState("");
  const [showSubmit, setShowSubmit] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  const visibleResults = searching ? results : [];

  /**
   * Submit an unlisted product (BUG-020).
   *
   * A marketplace link, not a name the reviewer invents. The API stores the row
   * `pending` for a moderator to name canonically — otherwise "Jisulife fan"
   * and "JISULIFE Life 9" become separate products and their reviews never
   * meet. The review can be written against it immediately either way.
   */
  async function submitByLink() {
    const url = sourceUrl.trim();
    if (!url || submitting) return;
    if (!/^https?:\/\//i.test(url)) {
      setError("Paste the full link, starting with https://");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch("/api/bff/api/v1/products", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name: query || url, source_url: url }),
      });
      if (!res.ok) {
        const p = (await res.json().catch(() => ({}))) as { detail?: string };
        setError(p.detail ?? "Couldn't submit that product.");
        return;
      }
      onPick(await res.json());
    } catch {
      setError("Couldn't reach the server.");
    } finally {
      setSubmitting(false);
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
      </ul>

      {searching && !busy ? (
        <div className="mt-4 rounded-[var(--radius-sm)] border border-dashed border-[var(--line-hairline-30)] p-4">
          {showSubmit ? (
            <>
              <p className="text-[13px] font-medium text-[var(--text-primary)]">
                Paste the Shopee or Lazada link
              </p>
              <p className="mt-1 text-[12px] text-[var(--text-secondary)]">
                A moderator names it properly so every review of this product
                ends up in one place. You can write your review right away.
              </p>
              <div className="relative mt-3">
                <LinkIcon
                  size={18}
                  className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
                />
                <input
                  value={sourceUrl}
                  onChange={(e) => setSourceUrl(e.target.value)}
                  placeholder="https://shopee.ph/…"
                  inputMode="url"
                  className={`${inputCls} pl-9`}
                />
              </div>
              {error ? (
                <p role="alert" className="mt-2 text-[12px] text-[var(--accent-danger)]">
                  {error}
                </p>
              ) : null}
              <div className="mt-3 flex gap-2">
                <Button
                  type="button"
                  size="sm"
                  onClick={submitByLink}
                  disabled={!sourceUrl.trim() || submitting}
                >
                  {submitting ? "Submitting…" : "Use this product"}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  onClick={() => setShowSubmit(false)}
                >
                  Back to search
                </Button>
              </div>
            </>
          ) : (
            <button
              type="button"
              onClick={() => setShowSubmit(true)}
              className="text-left"
            >
              <span className="text-[14px] text-[var(--text-primary)]">
                Can&rsquo;t find &ldquo;
                <span className="font-semibold">{query}</span>&rdquo;?
              </span>
              <span className="mt-0.5 block text-[12px] text-[var(--accent-primary)]">
                Add it with a marketplace link
              </span>
            </button>
          )}
        </div>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------- flow */

function StepsFlow({
  product,
  draft,
  patch,
  onChangeProduct,
  onDone,
}: {
  product: Product;
  draft: Draft;
  patch: (c: Partial<Draft>) => void;
  onChangeProduct: () => void;
  onDone: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const step = Math.min(draft.step, STEPS.length - 1);

  /**
   * What each step still needs before it can advance.
   *
   * Named per step so the button can say the reason rather than just sitting
   * there greyed out (BUG-001), and pros/cons is genuinely gating here rather
   * than optional-in-practice (BUG-021).
   */
  const blocker = ((): string | null => {
    switch (step) {
      case 0:
        return draft.discussion.trim().length < 40
          ? "Write at least a couple of sentences about your experience."
          : null;
      case 1:
        return draft.verdict ? null : "Pick a verdict.";
      case 2:
        return draft.rating > 0 ? null : "Give it a star rating.";
      case 3:
        return lines(draft.pros).length === 0 || lines(draft.cons).length === 0
          ? "Give at least one pro and one con — both are required."
          : null;
      case 4:
        return draft.anti.trim() ? null : "Say who should skip this one.";
      case 6:
        return draft.title.trim() ? null : "Give your review a title.";
      default:
        return null;
    }
  })();

  const isLast = step === STEPS.length - 1;

  async function submit() {
    if (blocker || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/bff/api/v1/reviews", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          product_id: product.id,
          title: draft.title.trim(),
          discussion: draft.discussion.trim(),
          verdict: draft.verdict,
          star_rating: draft.rating,
          target_audience: draft.target.trim() || null,
          anti_target_audience: draft.anti.trim() || null,
          pros: lines(draft.pros),
          cons: lines(draft.cons),
          photo_url: draft.photoUrl,
          receipt_key: draft.receiptKey,
          price_paid: draft.price.trim() ? Number(draft.price) : null,
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
        onClick={step === 0 ? onChangeProduct : () => patch({ step: step - 1 })}
        className="inline-flex items-center gap-1 text-[13px] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
      >
        <CaretLeft size={16} /> {step === 0 ? "Change product" : STEPS[step - 1]}
      </button>

      <div className="mt-4 flex items-center gap-3">
        <span className="text-[12px] font-medium text-[var(--text-muted)]">
          Step {step + 1} of {STEPS.length}
        </span>
        <div
          className="h-1 flex-1 overflow-hidden rounded-full bg-[var(--base-gray-200)]"
          role="progressbar"
          aria-valuenow={step + 1}
          aria-valuemin={1}
          aria-valuemax={STEPS.length}
          aria-label="Review progress"
        >
          <div
            className="h-full rounded-full bg-[var(--accent-primary)] transition-[width]"
            style={{ width: `${((step + 1) / STEPS.length) * 100}%` }}
          />
        </div>
      </div>

      <h1 className="mt-4 text-[22px] font-bold text-[var(--text-primary)]">
        {STEPS[step]}
      </h1>
      <p className="mt-1 text-[13px] text-[var(--text-secondary)]">
        Reviewing{" "}
        <span className="font-medium text-[var(--accent-primary)]">
          {product.canonical_name ?? "your product"}
        </span>
      </p>

      <div className="mt-6">
        {step === 0 ? (
          <Field label="Tell us what actually happened">
            <textarea
              value={draft.discussion}
              onChange={(e) =>
                patch({ discussion: e.target.value.slice(0, MAX_DISCUSSION) })
              }
              rows={9}
              autoFocus
              placeholder="How long have you used it? What surprised you? What would you tell a friend who was about to buy one?"
              className={`${inputCls} resize-y py-3`}
            />
            <Counter value={draft.discussion.length} max={MAX_DISCUSSION} />
          </Field>
        ) : null}

        {step === 1 ? (
          <div className="flex flex-col gap-3">
            {VERDICTS.map((v) => (
              <button
                key={v.value}
                type="button"
                onClick={() => patch({ verdict: v.value })}
                aria-pressed={draft.verdict === v.value}
                className="rounded-[var(--radius-sm)] p-4 text-left transition-shadow"
                style={
                  draft.verdict === v.value
                    ? { boxShadow: `inset 0 0 0 2px ${v.ring}` }
                    : { boxShadow: "inset 0 0 0 1px var(--line-hairline-30)" }
                }
              >
                <span
                  className="block text-[15px] font-semibold"
                  style={{
                    color:
                      draft.verdict === v.value ? v.ring : "var(--text-primary)",
                  }}
                >
                  {v.label}
                </span>
                <span className="mt-0.5 block text-[13px] text-[var(--text-secondary)]">
                  {v.hint}
                </span>
              </button>
            ))}
          </div>
        ) : null}

        {step === 2 ? (
          <div className="flex items-center gap-2">
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                key={n}
                type="button"
                onClick={() => patch({ rating: n })}
                aria-label={`${n} star${n > 1 ? "s" : ""}`}
                aria-pressed={draft.rating === n}
              >
                <Star
                  size={40}
                  weight={n <= draft.rating ? "fill" : "regular"}
                  className={
                    n <= draft.rating
                      ? "text-[var(--accent-star)]"
                      : "text-[var(--base-gray-300)]"
                  }
                />
              </button>
            ))}
          </div>
        ) : null}

        {step === 3 ? (
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Pros (one per line)">
              <textarea
                value={draft.pros}
                onChange={(e) => patch({ pros: e.target.value })}
                rows={5}
                autoFocus
                placeholder={"Genuinely quiet\nBattery lasts a full day"}
                className={`${inputCls} resize-y py-3`}
              />
            </Field>
            <Field label="Cons (one per line)">
              <textarea
                value={draft.cons}
                onChange={(e) => patch({ cons: e.target.value })}
                rows={5}
                placeholder={"Charging port feels flimsy\nNo case included"}
                className={`${inputCls} resize-y py-3`}
              />
            </Field>
          </div>
        ) : null}

        {step === 4 ? (
          <div className="flex flex-col gap-5">
            <Field label="Who should skip this?">
              <input
                value={draft.anti}
                onChange={(e) => patch({ anti: e.target.value })}
                autoFocus
                placeholder="Anyone who needs it to fit in a pocket"
                className={inputCls}
              />
            </Field>
            <Field label="Who is it right for? (optional)">
              <input
                value={draft.target}
                onChange={(e) => patch({ target: e.target.value })}
                placeholder="Commuters who want something light"
                className={inputCls}
              />
            </Field>
          </div>
        ) : null}

        {step === 5 ? (
          <div className="flex flex-col gap-6">
            <ReceiptField
              value={draft.receiptKey}
              onChange={(key) => patch({ receiptKey: key })}
            />
            <PhotoField
              label="A photo of the product (optional)"
              hint="Your own photo, not the seller's listing image."
              url={draft.photoUrl}
              onChange={(url) => patch({ photoUrl: url })}
            />
          </div>
        ) : null}

        {step === 6 ? (
          <div className="flex flex-col gap-5">
            <Field label="Review title">
              <input
                value={draft.title}
                onChange={(e) => patch({ title: e.target.value.slice(0, MAX_TITLE) })}
                autoFocus
                placeholder="Worth the money, or just overhyped?"
                className={inputCls}
              />
              <Counter value={draft.title.length} max={MAX_TITLE} />
            </Field>
            <Field label="What did you pay? (optional, ₱)">
              <input
                value={draft.price}
                onChange={(e) =>
                  patch({ price: e.target.value.replace(/[^0-9.]/g, "") })
                }
                inputMode="decimal"
                className={`${inputCls} max-w-[12rem]`}
                placeholder="899"
              />
            </Field>
          </div>
        ) : null}
      </div>

      {error ? (
        <p
          role="alert"
          className="mt-6 rounded-[var(--radius-sm)] bg-[color-mix(in_srgb,var(--accent-danger)_10%,transparent)] px-4 py-3 text-[13px] text-[var(--accent-danger)]"
        >
          {error}
        </p>
      ) : null}

      <div className="mt-8 flex flex-wrap items-center gap-3">
        <Button
          type="button"
          onClick={isLast ? submit : () => patch({ step: step + 1 })}
          disabled={Boolean(blocker) || busy}
        >
          {busy ? "Submitting…" : isLast ? "Submit for review" : "Continue"}
        </Button>
        {blocker ? (
          <p role="status" className="text-[12px] text-[var(--text-secondary)]">
            {blocker}
          </p>
        ) : isLast ? (
          <p className="text-[12px] text-[var(--text-muted)]">
            A moderator checks every review before it goes live.
          </p>
        ) : (
          <p className="text-[12px] text-[var(--text-muted)]">Saved as you type.</p>
        )}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ photos */

/**
 * One image, uploaded on selection (BUG-023).
 *
 * Uploading immediately rather than at submit means the reviewer sees straight
 * away whether the file was accepted — a rejection discovered at the end, after
 * seven steps, is the worst possible time to learn a photo was too large.
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
function ReceiptField({
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

function PhotoField({
  label,
  hint,
  url,
  onChange,
}: {
  label: string;
  hint: string;
  url: string | null;
  onChange: (url: string | null) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function pick(file: File) {
    setBusy(true);
    setError(null);
    try {
      // See ReceiptField: the real ceiling is the platform's, not the API's.
      const prepared = await prepareImageForUpload(file, "photo");
      if (prepared.error) {
        setError(prepared.error);
        return;
      }
      const body = new FormData();
      body.append("file", prepared.file);
      const res = await fetch("/api/bff/api/v1/reviews/photo", {
        method: "POST",
        body,
      });
      if (!res.ok) {
        const p = (await res.json().catch(() => ({}))) as { detail?: string };
        setError(p.detail ?? "That image couldn't be uploaded.");
        return;
      }
      const { url: uploaded } = (await res.json()) as { url: string };
      onChange(uploaded);
    } catch {
      setError("Couldn't reach the server.");
    } finally {
      setBusy(false);
      // Let the same file be re-picked after a failure.
      if (input.current) input.current.value = "";
    }
  }

  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[13px] font-medium text-[var(--text-primary)]">{label}</span>
      <span className="text-[12px] text-[var(--text-secondary)]">{hint}</span>

      {url ? (
        <div className="mt-2 flex items-start gap-3">
          {/* The uploaded object, so it goes through the optimizer. The
              *local* preview above stays a plain <img>: it is a blob: URL that
              never reaches the network. */}
          <Image
            src={url}
            alt="Uploaded preview"
            width={112}
            height={112}
            className="h-28 w-28 rounded-[var(--radius-sm)] object-cover shadow-[var(--shadow-hairline-inset)]"
          />
          <button
            type="button"
            onClick={() => onChange(null)}
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
        <p role="alert" className="text-[12px] text-[var(--accent-danger)]">
          {error}
        </p>
      ) : (
        <p className="text-[11px] text-[var(--text-muted)]">
          PNG, JPEG, or WebP. Up to 8 MB.
        </p>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ shared */

function Counter({ value, max }: { value: number; max: number }) {
  const near = value > max * 0.9;
  return (
    <span
      className={`self-end text-[11px] ${
        near ? "text-[var(--accent-danger)]" : "text-[var(--text-muted)]"
      }`}
    >
      {value.toLocaleString("en-PH")} / {max.toLocaleString("en-PH")}
    </span>
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
