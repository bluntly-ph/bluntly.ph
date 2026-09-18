"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useId, useMemo, useRef, useState, useSyncExternalStore } from "react";
import {
  ArrowRight,
  Check,
  Cloud,
  Equals,
  Image as ImageIcon,
  Plus,
  QuestionMark,
  User,
  X,
} from "@phosphor-icons/react/dist/ssr";
import type { Icon } from "@phosphor-icons/react";

import { ComposerGrid, ComposerHeader } from "@/components/reviews/ComposerHeader";
import {
  COMPOSER_ACTION_BUTTON,
  ComposerActions,
  ComposerLayout,
  ComposerSteps,
  type ComposerStep,
} from "@/components/reviews/ComposerLayout";
import { CurrentlyReviewingCard } from "@/components/reviews/CurrentlyReviewingCard";
import {
  MAX_TITLE,
  blockerFor,
  buttonLabel,
  counterIsSatisfied,
  counterLabel,
} from "@/components/reviews/composer-gate-model";
import { MascotPrompt } from "@/components/reviews/MascotPrompt";
import { DisclosureField } from "@/components/reviews/DisclosureField";
import type { MaterialRelationship } from "@/components/reviews/disclosure-model";
import { PriceCaptureCard } from "@/components/reviews/PriceCaptureCard";
import { pricePayload, type PricePlatform } from "@/components/reviews/price-capture-model";
import { ReceiptField } from "@/components/reviews/ReceiptField";
import { LatestStats } from "@/components/reviews/LatestStats";
import { ProductPicker, type PickedProduct } from "@/components/reviews/ProductPicker";
import { ReviewPreviewCard } from "@/components/reviews/ReviewPreviewCard";
import { DONE_CARDS, TiltedRatingCards } from "@/components/reviews/TiltedRatingCards";
import type { PanelUser } from "@/components/site/ProfileNavPanel";
import { Button } from "@/components/ui/Button";
import { StarRatingInput } from "@/components/ui/StarRatingInput";
import { prepareImageForUpload } from "@/lib/image";

type Product = PickedProduct;
type Verdict = "yes_absolutely" | "it_depends" | "hard_pass";

const VERDICTS: {
  value: Verdict;
  label: string;
  hint: string;
  ring: string;
  /** The glyph's own colour in Figma 4435:1092: green check, black equals, red X. */
  iconColor: string;
  Icon: Icon;
}[] = [
  {
    value: "yes_absolutely",
    label: "Yes, absolutely!",
    hint: "You'd tell a friend to buy it.",
    ring: "var(--accent-success)",
    iconColor: "var(--accent-success)",
    Icon: Check,
  },
  {
    value: "it_depends",
    label: "It depends",
    hint: "Right for some people, wrong for others.",
    ring: "var(--accent-star)",
    iconColor: "var(--base-black)",
    Icon: Equals,
  },
  {
    value: "hard_pass",
    label: "Hard pass",
    hint: "You'd tell a friend to save their money.",
    ring: "var(--accent-danger)",
    iconColor: "var(--accent-danger)",
    Icon: X,
  },
];

/**
 * The rating row is drawn as an arc: same-size stars whose vertical offset dips
 * away from the middle. Figma "Reviewer Page - Step 3.1" (4435:1344): five 52px
 * stars on a 60px pitch at y 370, 359, 354, 359, 370.
 */
const STAR_ARC = [16, 5, 0, 5, 16] as const;

/** Enforced in the API too (MAX_DISCUSSION_CHARS) — BUG-022. */
const MAX_DISCUSSION = 5000;

const lines = (s: string) =>
  s
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean)
    .slice(0, 10);

/* ------------------------------------------------------------------ draft */

/**
 * The draft (BUG-024, QA-003).
 *
 * Everything typed lives in one object so saving is a single write and
 * restoring is a single read. Version the key rather than migrating a shape: a
 * stale shape from an older build should be ignored, not half-applied to a form
 * whose fields have moved.
 *
 * v1 stored ONE draft under one key, and the autosave rewrote that key on every
 * keystroke. So starting a review of a second product silently destroyed the
 * first — the reviewer got one "unfinished review" banner naming whichever
 * product they had touched last, and no way back to the other. QA-003 found it
 * with two Tefal drafts; it applies to any two.
 *
 * v2 keeps a map, one entry per product, so drafts stop competing for a slot.
 */
const DRAFTS_KEY = "bluntly:review-drafts:v2";
const LEGACY_DRAFT_KEY = "bluntly:review-draft:v1";

/** The slot for work begun before a product was chosen. */
const UNPICKED = "__no-product__";

/**
 * A ceiling, so a reviewer who abandons many drafts cannot fill localStorage
 * and break saving for the draft they actually care about. Oldest goes first.
 */
const MAX_DRAFTS = 10;

function draftSlot(product: Product | null): string {
  return product?.id ?? UNPICKED;
}

type Draft = {
  step: number;
  product: Product | null;
  title: string;
  discussion: string;
  verdict: Verdict | null;
  /** 0 to 5 in half steps, null until the reviewer answers. */
  rating: number | null;
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
  // Where that price was paid. With a price it becomes a pending community
  // price observation; drafts saved before this field read it as null.
  pricePlatform: PricePlatform | null;
  // Disclosure of a material relationship (X.1). Drafts saved before this
  // field read it as null and the last step asks again.
  disclosure: MaterialRelationship | null;
  savedAt: number;
};

const EMPTY_DRAFT: Draft = {
  step: 0,
  product: null,
  title: "",
  discussion: "",
  verdict: null,
  rating: null,
  pros: "",
  cons: "",
  target: "",
  anti: "",
  photoUrl: null,
  receiptKey: null,
  price: "",
  pricePlatform: null,
  disclosure: null,
  savedAt: 0,
};

/** One stored draft, cleaned up, or null if it is not worth offering. */
function reviveDraft(parsed: Partial<Draft> | null | undefined): Draft | null {
  try {
    if (!parsed) return null;
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

/** Every stored draft, newest first. Reads the v1 key too, once. */
function readDrafts(): { slot: string; draft: Draft }[] {
  const found = new Map<string, Draft>();

  try {
    const raw = window.localStorage.getItem(DRAFTS_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as Record<string, Partial<Draft>>;
      for (const [slot, value] of Object.entries(parsed ?? {})) {
        const draft = reviveDraft(value);
        if (draft) found.set(slot, draft);
      }
    }
  } catch {
    /* see clearDraft */
  }

  // The v1 draft is worth one more read: a reviewer mid-review when this
  // shipped should not lose it. It is folded into the map and the old key
  // dropped, so this happens exactly once.
  try {
    const legacy = window.localStorage.getItem(LEGACY_DRAFT_KEY);
    if (legacy) {
      const draft = reviveDraft(JSON.parse(legacy) as Partial<Draft>);
      const slot = draftSlot(draft?.product ?? null);
      if (draft && !found.has(slot)) found.set(slot, draft);
      window.localStorage.removeItem(LEGACY_DRAFT_KEY);
    }
  } catch {
    /* see clearDraft */
  }

  return [...found.entries()]
    .map(([slot, draft]) => ({ slot, draft }))
    .sort((a, b) => (b.draft.savedAt ?? 0) - (a.draft.savedAt ?? 0));
}

function writeDraft(slot: string, draft: Draft) {
  try {
    const kept = readDrafts().filter((entry) => entry.slot !== slot);
    // Newest first, so the oldest fall off the end once the cap is reached.
    const next: Record<string, Draft> = { [slot]: draft };
    for (const entry of kept.slice(0, MAX_DRAFTS - 1)) next[entry.slot] = entry.draft;
    window.localStorage.setItem(DRAFTS_KEY, JSON.stringify(next));
  } catch {
    /* see clearDraft */
  }
}

function clearDraft(slot: string) {
  try {
    const next: Record<string, Draft> = {};
    for (const entry of readDrafts()) {
      if (entry.slot !== slot) next[entry.slot] = entry.draft;
    }
    window.localStorage.setItem(DRAFTS_KEY, JSON.stringify(next));
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
/**
 * Display copy for a step whose Figma frame specifies its own heading.
 *
 * `STEPS` doubles as the back-link label ("< Star rating"), so it has to stay
 * short. The frame for the Pros/Cons step gives that screen a title and a
 * credibility line of its own, which is what a reviewer actually reads — so it
 * is carried separately rather than by widening the navigation labels.
 *
 * Only this step could be compared against its frame: the Figma source is
 * behind an exhausted account quota, and the frame for it was available as a
 * capture. The other steps keep the existing pattern rather than being changed
 * on a guess.
 */
/**
 * Per-step heading and credibility line, transcribed from the owner's reference
 * pack (the "Reviewer Page - Step N" exports, which are the review composer
 * rather than any reviewer page).
 *
 * Indices 2..6 are here because those steps correspond exactly: the reference's
 * "Step 3 out of 7" is this form's index 2, and so on through step 7.
 *
 * Indices 0 and 1 are deliberately absent. The reference's step 1 is product
 * selection and its step 2 carries the verdict AND the written reason together,
 * where this form has the reason at index 0 and the verdict at index 1, with
 * product selection as an unnumbered phase before them. Giving those two steps
 * reference copy would attach the wrong words to the wrong screen; merging them
 * is a structural change that moves stored draft step numbers, so it is recorded
 * rather than smuggled into a copy change.
 */
const STEP_COPY: Record<number, { title: string; blurb: string }> = {
  0: {
    title: "Tell us your experience",
    blurb: "Your unfiltered words. Make it count.",
  },
  1: {
    title: "Your verdict",
    blurb: "Your unfiltered words. Make it count.",
  },
  2: {
    title: "Rating time",
    blurb: "Who doesn't love rating things they bought?",
  },
  3: {
    title: "The good, the bad",
    blurb: "Boost your review's credibility by adding key information people want to know",
  },
  4: {
    title: "No product is for everybody",
    blurb: "At bluntly, we believe that there's no such thing as a perfect product",
  },
  5: {
    title: "Show, don't tell",
    blurb: "A photo of the actual product verifies your review and is required for earning eligibility.",
  },
  6: {
    title: "Final touch",
    blurb: "This is what people see first. Make it stand out!",
  },
};

/**
 * Where each step's body starts under its blurb's 18px line, measured against
 * its frame: the product card at y174, the verdict bubble at 190, the pros card,
 * photo card and title field at 204 / 204 / 186, the crowd at 192. The stars
 * carry their own offset.
 */
const BODY_TOP = ["mt-[19px]", "mt-[35px]", "", "mt-[31px]", "mt-[19px]", "mt-[31px]", "mt-[31px]"] as const;

type Submitted = { productName: string | null; title: string; photoUrl: string | null };

const STEPS = [
  "Your experience",
  "Your verdict",
  "Star rating",
  "Pros and cons",
  "Who it's not for",
  "Proof of purchase",
  "Title",
] as const;

export function WriteReviewForm({ user }: { user: PanelUser }) {
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [product, setProduct] = useState<Product | null>(null);
  const [phase, setPhase] = useState<"product" | "steps" | "done">("product");
  // What was sent, for the All done screen's preview once the draft is cleared.
  const [submitted, setSubmitted] = useState<Submitted | null>(null);
  const router = useRouter();

  const hydrated = useHydrated();
  // Captured once, at hydration: the autosave below rewrites the same key on
  // every keystroke, and re-reading it would keep resurrecting the banner with
  // the reviewer's own in-progress work.
  const savedDrafts = useMemo(() => (hydrated ? readDrafts() : []), [hydrated]);
  // Slots the reviewer has already dealt with this visit — resumed or
  // discarded — so a banner does not reappear over the work it opened.
  const [handled, setHandled] = useState<string[]>([]);
  const resumable = savedDrafts.filter((entry) => !handled.includes(entry.slot));

  // Persist on every change, but only once there is something worth keeping.
  // Writing to an external store is what effects are for; no state is set here.
  useEffect(() => {
    if (!hydrated) return;
    if (!product && !draft.discussion.trim() && !draft.title.trim()) return;
    writeDraft(draftSlot(product), { ...draft, product, savedAt: Date.now() });
  }, [draft, product, hydrated]);

  const patch = useCallback((changes: Partial<Draft>) => setDraft((d) => ({ ...d, ...changes })), []);

  function resume(slot: string) {
    const saved = savedDrafts.find((entry) => entry.slot === slot)?.draft;
    if (!saved) return;
    setDraft(saved);
    setProduct(saved.product);
    setPhase(saved.product ? "steps" : "product");
    // Only this one is dealt with. Any other draft keeps its banner, so
    // switching between two unfinished reviews stays possible.
    setHandled((slots) => [...slots, slot]);
  }

  function discard(slot: string) {
    clearDraft(slot);
    setHandled((slots) => [...slots, slot]);
  }

  // What the header's arrow means right here. Inside the step flow it walks
  // back through the steps and then out to the product picker; on the first
  // and last screens there is no earlier step, so it leaves the composer.
  const step = Math.min(draft.step, STEPS.length - 1);
  const back =
    phase === "steps" && product
      ? step > 0
        ? { label: `Back to ${STEPS[step - 1]}`, run: () => patch({ step: step - 1 }) }
        : { label: "Change product", run: () => setPhase("product") }
      : { label: "Go back", run: () => router.back() };

  // A new step starts at its top. On the website the action sits under the
  // step, so without this the next step would open scrolled to wherever the
  // last one ended.
  useEffect(() => {
    window.scrollTo({ top: 0 });
  }, [step, phase]);

  const inSteps = phase === "steps" && product !== null;
  const panelSteps: ComposerStep[] = [
    {
      label: "Choose the product",
      state: phase === "product" ? "current" : "done",
      onSelect: inSteps ? () => setPhase("product") : undefined,
    },
    ...STEPS.map((label, i): ComposerStep => ({
      label,
      number: i + 1,
      state:
        phase === "done" ? "done" : !inSteps ? "todo" : i < step ? "done" : i === step ? "current" : "todo",
      onSelect: inSteps && i < step ? () => patch({ step: i }) : undefined,
    })),
  ];

  return (
    <>
      <ComposerHeader
        user={user}
        title="Write a review"
        onBack={back.run}
        backLabel={back.label}
        progress={phase === "done" ? 1 : phase === "steps" && product ? (step + 1) / STEPS.length : 0}
      />

      <ComposerGrid />
      <ComposerLayout
        aside={
          <ComposerSteps
            flow="Write a review"
            subjectLabel="Reviewing"
            subject={phase === "done" ? (submitted?.productName ?? null) : (product?.canonical_name ?? null)}
            steps={panelSteps}
            note={
              phase === "done"
                ? "A moderator checks every review before it goes public."
                : "Your draft is saved on this device as you type, so you can pick it up later."
            }
          />
        }
      >
        {phase === "done" ? (
          <DoneStep user={user} submitted={submitted} />
        ) : (
          <>
            <ResumeList drafts={resumable} onResume={resume} onDiscard={discard} />

            {phase === "product" ? (
              <ProductPicker
                title="What did you buy?"
                blurb="Find the product. Your review will matter."
                placeholder="e.g Jisulife Fanlife 9"
                searchLabel="Search for the product you bought"
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
                user={user}
                onChangeProduct={() => setPhase("product")}
                onDone={(snapshot) => {
                  clearDraft(draftSlot(product));
                  setSubmitted(snapshot);
                  setPhase("done");
                }}
              />
            ) : null}
          </>
        )}
      </ComposerLayout>
    </>
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
    <div className="flex items-start justify-between gap-3 rounded-[var(--radius-sm)] bg-[color-mix(in_srgb,var(--accent-primary)_8%,transparent)] p-4">
      <div className="min-w-0">
        <p className="text-[14px] font-semibold text-[var(--text-primary)]">
          {draft.product?.canonical_name
            ? `Unfinished review of ${draft.product.canonical_name}`
            : "Unfinished review"}
        </p>
        {when ? <p className="mt-1 text-[12px] text-[var(--text-secondary)]">Saved {when}.</p> : null}
      </div>
      <div className="flex shrink-0 gap-2">
        <Button type="button" size="sm" onClick={onResume}>
          Pick up
        </Button>
        <Button type="button" size="sm" variant="secondary" onClick={onDiscard}>
          Discard
        </Button>
      </div>
    </div>
  );
}

/**
 * Every unfinished review, not just the last one touched.
 *
 * One banner per draft. A reviewer with drafts of two products has to be able
 * to see both — a single banner naming one of them is how QA-003's second Tefal
 * draft "disappeared": it was there, it just had nothing pointing at it.
 */
function ResumeList({
  drafts,
  onResume,
  onDiscard,
}: {
  drafts: { slot: string; draft: Draft }[];
  onResume: (slot: string) => void;
  onDiscard: (slot: string) => void;
}) {
  if (drafts.length === 0) return null;
  return (
    <div className="mb-6 flex flex-col gap-2">
      {drafts.length > 1 ? (
        <p className="text-[13px] text-[var(--text-secondary)]">
          You have {drafts.length} unfinished reviews.
        </p>
      ) : null}
      {drafts.map(({ slot, draft }) => (
        <ResumeBanner
          key={slot}
          draft={draft}
          onResume={() => onResume(slot)}
          onDiscard={() => onDiscard(slot)}
        />
      ))}
    </div>
  );
}

/* -------------------------------------------------------------- pros/cons */

/**
 * Suggested phrases for step 4 (QA-002).
 *
 * The approved design offers these as one-tap chips; the live form offered a
 * bare "one per line" textarea, which is a blank page at the exact moment a
 * reviewer is least sure what to write. The wording is the design's own.
 *
 * They are a STARTING POINT, not a vocabulary: the free-text field below them
 * is equally prominent, and a typed phrase is stored identically to a tapped
 * one. Restricting reviews to a fixed set of phrases would flatten the specific
 * detail that makes a review worth reading.
 */
const PRO_SUGGESTIONS = [
  "Worth it!",
  "Good build quality",
  "Portable",
  "Affordable",
  "Feels premium",
  "Easy to use",
];

const CON_SUGGESTIONS = [
  "Not worth it",
  "Too expensive",
  // "Too Heavy" and "Feels cheap" are in the reference's con list and were
  // missing here, so two of the seven drawn chips could not be tapped. The
  // capital H is the frame's own.
  "Too Heavy",
  "Feels cheap",
  "Flimsy",
  "Not as advertised",
  "Looks better in the photos",
];

/**
 * Step 7's title field: Figma "Reviewer Page - Step 7" (4452:748), read
 * 2026-09-15 — a 53px white field at radius 16, the placeholder "Your
 * interesting title here..." 16px in, in 14px Regular at 30% ink, and the
 * counter 4px under it, right-aligned, in 10px Light.
 *
 * There is no visible label — the frame shows placeholder text only — so the
 * real label is present and hidden rather than dropped: a placeholder is not
 * an accessible name and it disappears the moment you type.
 */
function TitleField({ value, onChange }: { value: string; onChange: (next: string) => void }) {
  const id = useId();
  return (
    <div>
      <label className="sr-only" htmlFor={id}>
        Review title
      </label>
      <input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value.slice(0, MAX_TITLE))}
        autoFocus
        placeholder="Your interesting title here..."
        className="h-[53px] w-full rounded-[16px] bg-[var(--surface-card)] px-4 text-[14px] text-[var(--text-primary)] shadow-[var(--shadow-card)] outline-none placeholder:text-[rgba(32,32,32,0.3)] focus-visible:shadow-[var(--shadow-card),inset_0_0_0_1px_var(--accent-primary)]"
      />
      <p className="mt-1 text-right text-[10px] font-light leading-none text-[var(--text-primary)]">
        {value.length}/{MAX_TITLE} characters
      </p>
    </div>
  );
}

/**
 * Step 6: one upload target, the whole card.
 *
 * Figma "Reviewer Page - Step 6" (4443:555), read 2026-09-15: a 390px white
 * card at radius 16; the 64px Image glyph in black 90px down; "Tap to upload
 * your product photo" in 14px Regular 8px under it and "Use your own photo of
 * the product" in 12px Regular at 30% ink 11px lower; "Skip – I'll add a photo
 * later" in 14px Regular 20px under the card. In 6.1 the photo covers the card
 * edge to edge, same rounding.
 *
 * Continue is grey in 6 and orange in 6.1, so the photo gates the step and
 * Skip is the way past it.
 *
 * The frame has one upload, its blurb assigns verification to it ("A photo of
 * the actual product verifies your review and is required for earning
 * eligibility"), and step 7 draws that same photo on the public review card —
 * so the card is the product photo. The proof-of-purchase upload is ALSO
 * collected, beneath it: the photo is public and decides *verified* status;
 * the receipt is private, moderator-only, and the only input to the
 * earn_eligible gate, which reads `receipt_key` and nothing else. An earlier
 * pass mounted only the photo, to match the frame, and left every submission
 * posting receipt_key: null (fixed in b2f1e29; owner confirmed both are
 * required, 2026-09-14).
 */
function ProductPhotoCard({
  url,
  onChange,
  onSkip,
  receiptKey,
  onReceiptChange,
}: {
  url: string | null;
  onChange: (url: string | null) => void;
  onSkip: () => void;
  receiptKey: string | null;
  onReceiptChange: (key: string | null) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function pick(file: File) {
    setBusy(true);
    setError(null);
    try {
      const prepared = await prepareImageForUpload(file, "photo");
      if (prepared.error) {
        setError(prepared.error);
        return;
      }
      const body = new FormData();
      body.append("file", prepared.file);
      const res = await fetch("/api/bff/api/v1/reviews/photo", { method: "POST", body });
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
    <div>
      <button
        type="button"
        onClick={() => input.current?.click()}
        disabled={busy}
        aria-label={url ? "Replace your product photo" : "Upload your product photo"}
        className="relative block h-[390px] w-full cursor-pointer overflow-hidden rounded-[16px] bg-[var(--surface-card)] shadow-[var(--shadow-card)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-primary)] disabled:cursor-wait"
      >
        {url ? (
          <Image src={url} alt="" fill sizes="358px" className="object-cover" />
        ) : (
          <span className="flex h-full flex-col items-center pt-[90px]">
            <ImageIcon size={64} weight="fill" aria-hidden="true" className="text-[var(--base-black)]" />
            <span className="mt-2 text-[14px] leading-none text-[var(--text-primary)]">
              {busy ? "Uploading…" : "Tap to upload your product photo"}
            </span>
            <span className="mt-[11px] text-[12px] leading-none text-[rgba(32,32,32,0.3)]">
              Use your own photo of the product
            </span>
          </span>
        )}
      </button>

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

      <button
        type="button"
        onClick={onSkip}
        className="mt-5 block w-full cursor-pointer text-center text-[14px] leading-none text-[var(--text-primary)] underline-offset-4 hover:underline"
      >
        Skip &ndash; I&apos;ll add a photo later
      </button>

      {/* INTENTIONAL PRODUCT DIFFERENCE — REQUIRED FUNCTIONALITY.
          The frame draws one upload. The product needs two, and they are not
          interchangeable: the photo above is public and decides *verified*
          status, while this one is proof of purchase — private, moderator-only,
          and the sole input to the earn_eligible gate, which reads
          `receipt_key` and nothing else. Treating the public product image as
          the receipt would be faking verification.

          So the step keeps the frame's card as the primary target and adds the
          receipt beneath it in the same visual language, clearly labelled,
          rather than dropping a required capability to reproduce a still. */}
      <div className="mt-8 border-t border-[var(--line-hairline-10)] pt-6">
        <ReceiptField value={receiptKey} onChange={onReceiptChange} />
      </div>

      {error ? (
        <p role="alert" className="mt-3 text-center text-[13px] text-[var(--accent-danger)]">
          {error}
        </p>
      ) : null}
    </div>
  );
}

/**
 * The clouds behind step 3's stars: Figma "Reviewer Page - Step 3.1" (4435:1344)
 * places eleven Icon/Cloud glyphs — Phosphor Cloud, 24 to 64px, several turned
 * 180deg — in a 1px outline at 20% ink. Coordinates are the frame's, relative
 * to the step body, which starts under the blurb. MOBILE ONLY: there is no
 * desktop frame to place them against. Decorative and unclickable.
 */
const CLOUDS: { left: number; top: number; size: number; flip?: boolean }[] = [
  { left: 24, top: 74, size: 32 },
  { left: -2, top: 325, size: 32 },
  { left: 30, top: 300, size: 52 },
  { left: 62, top: 36, size: 64 },
  { left: 255, top: 213, size: 64 },
  { left: 321, top: 277, size: 32, flip: true },
  { left: 341, top: 74, size: 32, flip: true },
  { left: 96, top: 309, size: 24, flip: true },
  { left: 243, top: 443, size: 32, flip: true },
  { left: 191, top: 398, size: 52, flip: true },
  { left: 153, top: 483, size: 24 },
];

function RatingStepDecor() {
  return (
    // The frame's clouds, at every width. Their coordinates belong to its 358px
    // content box, so on a wider column the box is centred on the stars rather
    // than stretched — the clouds keep their own scale and spacing.
    <span
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 -z-10 hidden select-none max-sm:block md:left-1/2 md:right-auto md:block md:w-[358px] md:-translate-x-1/2"
    >
      {CLOUDS.map((c, i) => (
        <Cloud
          key={i}
          size={c.size}
          weight="thin"
          className={`absolute text-[rgba(32,32,32,0.2)] ${c.flip ? "rotate-180" : ""}`}
          style={{ left: c.left, top: c.top }}
        />
      ))}
    </span>
  );
}

/**
 * The crowd behind step 5's mascot: Figma "Reviewer Page - Step 5" (4519:5414)
 * fills a 192px band edge to edge with Icon/User — Phosphor User at 32px in a
 * 1px outline at 30% ink — six rows of twenty, about 20px apart, every other
 * figure dropped 5px. Drawn from the glyph rather than a texture. Decorative.
 *
 * On the phone it bleeds to the screen edges. On the website it would bleed
 * into the side panel's gutter, so from `md` it is the column's width with
 * rounded ends, and each row carries enough figures to fill 42rem.
 */
const CROWD_ROWS = [0, 32, 62, 93, 125, 155];

function CrowdBand() {
  return (
    <span
      aria-hidden="true"
      className="pointer-events-none absolute -left-4 -right-4 top-0 -z-10 h-[192px] select-none overflow-hidden sm:-left-6 sm:-right-6 md:left-0 md:right-0 md:rounded-[16px]"
    >
      {CROWD_ROWS.flatMap((top, row) =>
        Array.from({ length: 34 }, (_, i) => (
          <User
            key={`${row}-${i}`}
            size={32}
            weight="thin"
            className="absolute text-[rgba(32,32,32,0.3)]"
            style={{ left: (row % 3 === 0 ? -14 : -13) + i * 20.3, top: top + (i % 2 ? 5 : 0) }}
          />
        )),
      )}
    </span>
  );
}

/**
 * The frame's big write-it-here card, shared by step 1 and step 5: Figma
 * "Reviewer Page - Step 1.1" (4435:863) and "Step 5" (4519:5414), read
 * 2026-09-15 — a 358x231 white card at radius 16 with the card shadow, the text
 * 20px in and 16px down in 14px Regular on a 21px line, the placeholder "Write
 * it *bluntly* here..." at 30% ink with the one word in italics, and the
 * counter 4px under the card, right-aligned, in 10px Light.
 *
 * The counter is the step's gate written down. Empty, both read "30
 * characters remaining"; satisfied, step 1 reads "Solid review!" and step 5
 * "I'm sure someone will appreciate this", in orange, and Continue turns orange
 * at the same moment. So 30 is a floor, not a limit.
 *
 * The card grows with the text (`field-sizing: content`); where that is
 * unsupported it stays at its minimum and scrolls. The italic word rules out
 * the placeholder attribute, so it is an overlay, and the real label stays.
 */
function BluntlyTextarea({
  label,
  value,
  onChange,
  satisfied,
  autoFocus = false,
  className = "",
}: {
  label: string;
  value: string;
  onChange: (next: string) => void;
  satisfied: string;
  autoFocus?: boolean;
  className?: string;
}) {
  const id = useId();

  return (
    <div className={className}>
      <label className="sr-only" htmlFor={id}>
        {label}
      </label>
      <div className="relative">
        <textarea
          id={id}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          autoFocus={autoFocus}
          className="field-sizing-content block min-h-[231px] w-full resize-none rounded-[16px] bg-[var(--surface-card)] px-5 py-4 text-[14px] leading-[21px] text-[var(--text-primary)] shadow-[var(--shadow-card)] outline-none focus-visible:shadow-[var(--shadow-card),inset_0_0_0_1px_var(--accent-primary)]"
        />
        {value.length === 0 ? (
          <span
            aria-hidden="true"
            className="pointer-events-none absolute left-5 top-4 text-[14px] leading-[21px] text-[rgba(32,32,32,0.3)]"
          >
            Write it <em>bluntly</em> here...
          </span>
        ) : null}
      </div>
      <p
        aria-live="polite"
        className={`mt-1 text-right text-[10px] font-light leading-none ${
          counterIsSatisfied(value) ? "text-[var(--accent-primary)]" : "text-[var(--text-primary)]"
        }`}
      >
        {counterLabel(value, satisfied)}
      </p>
    </div>
  );
}

/**
 * "Who is it right for?" — the other half of FR-3's audience pair.
 *
 * INTENTIONAL PRODUCT DIFFERENCE — REQUIRED FUNCTIONALITY. Not in the frame:
 * FR-3 lists the structured format as "all required" and names target
 * audience in it, and `reviews.target_audience` is a real column, so the field
 * stays, drawn like the step's other fields — 12px Light prompt, a 53px white
 * field at radius 16, 14px Regular with the placeholder at 30% ink.
 */
function TargetAudienceField({ value, onChange }: { value: string; onChange: (next: string) => void }) {
  const id = useId();
  return (
    <div className="mt-6">
      <label htmlFor={id} className="block text-[12px] font-light leading-[18px] text-[rgba(32,32,32,0.7)]">
        And who is it right for?
      </label>
      <input
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Commuters who want something light"
        className="mt-2 h-[53px] w-full rounded-[16px] bg-[var(--surface-card)] px-4 text-[14px] text-[var(--text-primary)] shadow-[var(--shadow-card)] outline-none placeholder:text-[rgba(32,32,32,0.3)] focus-visible:shadow-[var(--shadow-card),inset_0_0_0_1px_var(--accent-primary)]"
      />
    </div>
  );
}

/**
 * The chip shell, Figma "Reviewer Page - Step 4" (4512:5073): 52px tall, white
 * at 30% over the card, radius 12, 16px sides, a 20px Plus 8px before 14px
 * Regular, and a soft 0 4px 4px shadow at 10%.
 */
const CHIP_SHELL =
  "inline-flex h-[52px] items-center gap-2 rounded-[12px] bg-[rgba(255,255,255,0.3)] px-4 text-[14px] leading-none " +
  "shadow-[0_4px_4px_0_var(--shadow-color-10)]";

/**
 * The plus in front of a chip's label: #8c8c8c at rest, as drawn; a chosen
 * phrase takes its column's colour on the glyph and brand orange on the label.
 */
function ChipPlus({ color }: { color: string }) {
  return <Plus size={20} weight="light" aria-hidden="true" className="shrink-0" style={{ color }} />;
}

/**
 * Chips plus free text, over the same newline-joined string the draft and the
 * submit payload already use — so nothing downstream changes shape.
 *
 * The card, Figma 4512:5073: --surface-app at radius 12 with the card shadow,
 * 20px in; the column name in 12px Regular (trust blue for Pros, danger red for
 * Cons), the prompt 5px under it in 12px Light at 70%, and the chips 14px lower
 * with 12px between them.
 */
function PhrasePicker({
  tone,
  label,
  prompt,
  suggestions,
  addLabel,
  value,
  onChange,
}: {
  tone: "pro" | "con";
  label: string;
  prompt: string;
  suggestions: string[];
  addLabel: string;
  value: string;
  onChange: (next: string) => void;
}) {
  const [custom, setCustom] = useState("");
  const addId = useId();
  const chosen = lines(value);
  const has = (phrase: string) => chosen.some((c) => c.toLowerCase() === phrase.toLowerCase());

  function toggle(phrase: string) {
    const next = has(phrase)
      ? chosen.filter((c) => c.toLowerCase() !== phrase.toLowerCase())
      : [...chosen, phrase];
    onChange(next.join("\n"));
  }

  function addCustom() {
    const phrase = custom.trim();
    if (!phrase || has(phrase)) {
      setCustom("");
      return;
    }
    onChange([...chosen, phrase].join("\n"));
    setCustom("");
  }

  // Typed phrases render as chips too, so a reviewer can remove one the same
  // way they added it rather than hunting through a textarea.
  const extras = chosen.filter((c) => !suggestions.some((s) => s.toLowerCase() === c.toLowerCase()));
  const accent = tone === "pro" ? "text-[var(--accent-trust)]" : "text-[var(--accent-danger)]";

  return (
    <div className="rounded-[12px] bg-[var(--surface-app)] px-5 pb-7 pt-5 shadow-[var(--shadow-card)]">
      <p className={`text-[12px] leading-none ${accent}`}>{label}</p>
      <p className="mt-[5px] text-[12px] font-light leading-none text-[rgba(32,32,32,0.7)]">{prompt}</p>

      {/* 8px across, 12px down: at 12px across the frame's first pair of pros
          ("Worth it!", "Good build quality") no longer fits one 318px row. */}
      <ul className="mt-[14px] flex flex-wrap gap-x-2 gap-y-3">
        {[...suggestions, ...extras].map((phrase) => {
          const on = has(phrase);
          return (
            <li key={phrase}>
              <button
                type="button"
                onClick={() => toggle(phrase)}
                aria-pressed={on}
                className={`${CHIP_SHELL} cursor-pointer transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)] ${
                  on ? "text-[var(--accent-primary)]" : "text-[var(--text-primary)]"
                }`}
              >
                <ChipPlus
                  color={
                    on
                      ? tone === "pro"
                        ? "var(--accent-success)"
                        : "var(--accent-danger)"
                      : "var(--base-gray-400)"
                  }
                />
                {phrase}
              </button>
            </li>
          );
        })}
      </ul>

      {/* The frame draws this as one more chip, the full row wide, that
          happens to accept typing. A placeholder is not an accessible name,
          so the real label is still there, visually hidden. */}
      <div className={`mt-3 ${CHIP_SHELL} w-full text-[var(--text-primary)]`}>
        <ChipPlus color="var(--base-gray-400)" />
        <label className="sr-only" htmlFor={addId}>
          {addLabel}
        </label>
        <input
          id={addId}
          value={custom}
          onChange={(e) => setCustom(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              // The picker sits inside the step form; Enter adds a phrase here
              // rather than advancing the step.
              e.preventDefault();
              addCustom();
            }
          }}
          onBlur={addCustom}
          placeholder={addLabel}
          className="min-w-0 flex-1 bg-transparent outline-none placeholder:text-[rgba(32,32,32,0.3)]"
        />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------- flow */

function StepsFlow({
  product,
  draft,
  patch,
  user,
  onChangeProduct,
  onDone,
}: {
  product: Product;
  draft: Draft;
  patch: (c: Partial<Draft>) => void;
  /** Step 7's preview draws the reviewer's own name and avatar. */
  user: PanelUser;
  /** Step 1's card offers "Change" beside the product name. */
  onChangeProduct: () => void;
  onDone: (submitted: Submitted) => void;
}) {
  const [busy, setBusy] = useState(false);
  /** Synchronous double-submit guard — see `submit` (BUG-031). */
  const inFlight = useRef(false);
  // "Let's talk money" — the reference asks for the price on the way to
  // submitting rather than as a field on the title step.
  const [askingPrice, setAskingPrice] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const step = Math.min(draft.step, STEPS.length - 1);

  /**
   * What each step still needs before it can advance.
   *
   * Named per step so the button can say the reason rather than just sitting
   * there greyed out (BUG-001), and pros/cons is genuinely gating here rather
   * than optional-in-practice (BUG-021).
   */
  const blocker = blockerFor(step, draft);

  const isLast = step === STEPS.length - 1;

  async function submit() {
    // A ref, not the `busy` state, and checked before anything awaits (BUG-031).
    // Two taps in quick succession are two events, and React may not have
    // re-rendered between them — so `busy` can still read false in the second
    // one and the disabled attribute can still be a render behind. A ref is
    // written synchronously, which is what makes this a guard rather than a
    // race the user usually loses. The server refuses a second pending review
    // for the same product regardless; this stops the request being made at
    // all, so the reviewer never sees a conflict they did not cause.
    if (blocker || busy || inFlight.current) return;
    inFlight.current = true;
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
          // price_paid and price_platform together, or neither; with both the
          // API also files a pending community price observation.
          ...pricePayload(draft.price, draft.pricePlatform),
          material_relationship: draft.disclosure,
        }),
      });
      if (!res.ok) {
        const p = (await res.json().catch(() => ({}))) as { detail?: string };
        setError(p.detail ?? "Something went wrong submitting your review.");
        // The card stays open so the error is read where the action was taken.
        return;
      }
      setAskingPrice(false);
      onDone({
        productName: product.canonical_name,
        title: draft.title.trim(),
        photoUrl: draft.photoUrl,
      });
    } catch {
      setError("Couldn't reach the server. Try again.");
    } finally {
      setBusy(false);
      // Released only here, so a failed submission can be retried — the guard
      // is against a double tap, not against ever trying again.
      inFlight.current = false;
    }
  }

  return (
    <div>
      {/* Figma "Reviewer Page - Step N" (4435:863 … 4452:748), read 2026-09-15:
          "Step N out of 7" in 12px Regular 16px under the bar; the title 10px
          lower in 20px Medium brand orange; the blurb 10px lower in 12px Light
          at 70% on an 18px line. Each step's body then starts where its frame
          puts it. */}
      <p className="text-[12px] leading-none text-[var(--text-primary)]">
        Step {step + 1} out of {STEPS.length}
      </p>

      <h1 className="mt-2.5 text-[20px] font-medium leading-none text-[var(--accent-primary)]">
        {STEP_COPY[step]?.title ?? STEPS[step]}
      </h1>
      {STEP_COPY[step] ? (
        <p className="mt-[7px] text-[12px] font-light leading-[18px] text-[rgba(32,32,32,0.7)]">
          {STEP_COPY[step].blurb}
        </p>
      ) : null}

      <div className={BODY_TOP[step] ?? "mt-5"}>
        {step === 0 ? (
          <>
            <CurrentlyReviewingCard name={product.canonical_name} onChange={onChangeProduct} />
            <BluntlyTextarea
              label="Tell us your experience"
              value={draft.discussion}
              onChange={(discussion) => patch({ discussion: discussion.slice(0, MAX_DISCUSSION) })}
              satisfied="Solid review!"
              autoFocus
              className="mt-4"
            />
          </>
        ) : null}

        {step === 1 ? (
          <div className="relative isolate">
            {/* The frame's two Icon/QuestionMark glyphs at 10% ink either side
                of Bunbun (4435:1092). */}
            <QuestionMark
              size={32}
              weight="thin"
              aria-hidden="true"
              className="pointer-events-none absolute left-[26px] top-[53px] -z-10 text-[var(--line-hairline-10)]"
            />
            <QuestionMark
              size={32}
              weight="thin"
              aria-hidden="true"
              className="pointer-events-none absolute left-[310px] top-[69px] -z-10 text-[var(--line-hairline-10)]"
            />
            {/* One mascot for the whole step. Frame 2.2 draws the full
                illustration once a verdict is picked, but swapping it mid-answer
                read as the mascot changing out of nowhere (owner review,
                2026-09-16), so only the prompt's words react. */}
            <MascotPrompt className="mb-5" variant="simple">
              {draft.verdict ? "Woah, mind telling us why?" : "Would you recommend this to a friend?"}
            </MascotPrompt>
            {/* 53px white answers at radius 16, 12px apart: a 20px glyph 16px in
                and the label in 14px Regular 12px after it. The chosen one takes
                its verdict's colour as a ring. */}
            <div className="flex flex-col gap-3">
              {VERDICTS.map((v) => {
                const selected = draft.verdict === v.value;
                return (
                  <button
                    key={v.value}
                    type="button"
                    onClick={() => patch({ verdict: v.value })}
                    aria-pressed={selected}
                    className="flex h-[53px] cursor-pointer items-center gap-3 rounded-[16px] bg-[var(--surface-card)] px-4 text-left shadow-[var(--shadow-card)] transition-shadow focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]"
                    style={
                      selected ? { boxShadow: `var(--shadow-card), inset 0 0 0 2px ${v.ring}` } : undefined
                    }
                  >
                    <v.Icon
                      size={20}
                      weight={v.value === "it_depends" ? "regular" : "bold"}
                      aria-hidden="true"
                      className="shrink-0"
                      style={{ color: v.iconColor }}
                    />
                    <span
                      className="text-[14px] leading-none"
                      style={{ color: selected ? v.ring : "var(--text-primary)" }}
                    >
                      {v.label}
                    </span>
                    <span className="sr-only">{v.hint}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}

        {step === 2 ? (
          // No card here: frame 4435:1344 draws the stars on the page under its
          // clouds, and the white stage an earlier desktop pass added read as a
          // blank block under the rating (owner, 2026-09-16).
          <div className="relative isolate md:pb-10">
            <RatingStepDecor />
            {/* Figma 4435:1344: five 52px stars on a 60px pitch, the middle one
                highest and the outer pair 16px lower; empty ones #8c8c8c, chosen
                ones the rating ladder's colour for the value picked (Icon/Star:
                1–2 coral, 3 yellow, 4–5 green). The top of the arc is 154px
                under the blurb. Half steps and zero are the owner's requirement
                of 2026-09-16; the control is StarRatingInput. */}
            <StarRatingInput
              className="mt-[154px] md:mt-0"
              label="Star rating"
              value={draft.rating}
              onChange={(rating) => patch({ rating })}
              size={52}
              gap={8}
              arc={STAR_ARC}
            />
          </div>
        ) : null}

        {step === 3 ? (
          <div className="grid gap-7 sm:grid-cols-2">
            <PhrasePicker
              tone="pro"
              label="Pros"
              prompt="What's so great about this product?"
              suggestions={PRO_SUGGESTIONS}
              addLabel="Add a pro…"
              value={draft.pros}
              onChange={(pros) => patch({ pros })}
            />
            <PhrasePicker
              tone="con"
              label="Cons"
              prompt="What are the downsides worth mentioning?"
              suggestions={CON_SUGGESTIONS}
              addLabel="Add a con…"
              value={draft.cons}
              onChange={(cons) => patch({ cons })}
            />
          </div>
        ) : null}

        {step === 4 ? (
          <div className="relative isolate">
            <CrowdBand />
            {/* "not" is bold, underlined and the danger red in the frame. */}
            <MascotPrompt variant="simple" className="pt-[62px]">
              Who should <strong className="font-bold text-[var(--accent-danger)] underline">not</strong> buy
              this?
            </MascotPrompt>

            <BluntlyTextarea
              label="Who should not buy this?"
              value={draft.anti}
              onChange={(anti) => patch({ anti })}
              satisfied="I'm sure someone will appreciate this"
              className="mt-8"
            />

            <TargetAudienceField value={draft.target} onChange={(target) => patch({ target })} />
          </div>
        ) : null}

        {step === 5 ? (
          <ProductPhotoCard
            url={draft.photoUrl}
            onChange={(url) => patch({ photoUrl: url })}
            onSkip={() => patch({ step: step + 1 })}
            receiptKey={draft.receiptKey}
            onReceiptChange={(receiptKey) => patch({ receiptKey })}
          />
        ) : null}

        {step === 6 ? (
          <>
            <TitleField value={draft.title} onChange={(title) => patch({ title })} />
            <DisclosureField value={draft.disclosure} onChange={(disclosure) => patch({ disclosure })} />
            <ReviewPreviewCard
              username={user?.username ?? null}
              avatarUrl={user?.avatarUrl ?? null}
              productName={product.canonical_name}
              title={draft.title}
              photoUrl={draft.photoUrl}
            />
          </>
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

      <PriceCaptureCard
        open={askingPrice}
        price={draft.price}
        platform={draft.pricePlatform}
        busy={busy}
        error={error}
        onPriceChange={(price) => patch({ price })}
        onPlatformChange={(pricePlatform) => patch({ pricePlatform })}
        onSubmit={submit}
        onCancel={() => setAskingPrice(false)}
      />

      {/* Anchored to the bottom of the viewport, not to the end of the step.
          Measured identically in every frame that has one — steps 2, 4, 4.1,
          5, 6, 7 and 7.1 — at x16..373 (w358) and y756..811 (h56) inside an
          844-tall device. Step 4's frame is 1130 tall and still draws it at
          y756, which is what makes it the viewport and not the content that
          it is pinned to. The step content carries 120px of bottom padding so
          the pill never traps anything underneath it.

          The frames draw no helper text beside the button, so neither does
          this — but a disabled control still has to say why, so the reason
          moved into a live region instead of off the screen entirely.

          The website has no frame: there the pill sits inline under the step
          with the reason beside it (ComposerActions). */}
      <ComposerActions hint={blocker}>
        <Button
          type="button"
          onClick={isLast ? () => setAskingPrice(true) : () => patch({ step: step + 1 })}
          disabled={Boolean(blocker) || busy}
          fullWidth
          className={COMPOSER_ACTION_BUTTON}
        >
          {buttonLabel(step, STEPS.length, busy)}
          {busy ? null : <ArrowRight size={20} aria-hidden="true" />}
        </Button>
      </ComposerActions>
      <p role="status" className="sr-only">
        {blocker ?? "Saved as you type."}
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ shared */

/**
 * The All done screen, Figma "Reviewer Page - All done" (4550:8882), read
 * 2026-09-15: "All done!" in 12px Regular, the headline in 20px Medium brand
 * orange, the blurb in 12px Light at 70%; "See what your review looks like:"
 * in 12px Regular trust blue over the tilted preview card; "Your latest stats:"
 * over three figures in 28px Medium brand orange with 12px Light labels, 20px
 * apart; the full-width pill 32px from the bottom.
 *
 * INTENTIONAL PRODUCT DIFFERENCES:
 *  - The frame says "Your review is now live!" and "View my review". It is not
 *    live: every review is held for moderation first. So the layout is the
 *    frame's and the words are true — "submitted", with the check stated — and
 *    the pill opens the reviewer's own profile, where the pending review is
 *    listed and marked "Pending moderation". It used to open
 *    /dashboard/history, which lists earnings and never showed a pending
 *    review; and until 2026-09-18 the profile read the public feed, so the
 *    review was missing there too.
 *  - The stats are the reviewer's real dashboard figures over the last 90 days
 *    (GET /users/me/dashboard), not the frame's sample numbers, and the block is
 *    left out when they cannot be read.
 */
function DoneStep({ user, submitted }: { user: PanelUser; submitted: Submitted | null }) {
  return (
    <div className="relative">
      <TiltedRatingCards
        cards={DONE_CARDS}
        className="fixed inset-x-0 bottom-0 z-0 hidden h-[340px] max-sm:block"
      />
      <div className="relative z-10">
        <p className="text-[12px] leading-none text-[var(--text-primary)]">All done!</p>
        <h1 className="mt-2.5 text-[20px] font-medium leading-none text-[var(--accent-primary)]">
          Your review has been submitted!
        </h1>
        <p className="mt-[7px] text-[12px] font-light leading-[18px] text-[rgba(32,32,32,0.7)]">
          A moderator checks every review before it goes public. You&rsquo;ll hear from us once it&rsquo;s
          been through.
        </p>

        {submitted ? (
          <>
            <p className="mt-8 text-[12px] leading-none text-[var(--accent-trust)]">
              See what your review looks like:
            </p>
            <ReviewPreviewCard
              username={user?.username ?? null}
              avatarUrl={user?.avatarUrl ?? null}
              productName={submitted.productName}
              title={submitted.title}
              photoUrl={submitted.photoUrl}
              className="mt-[18px] md:max-w-[26rem]"
            />
          </>
        ) : null}

        <LatestStats className="mt-[35px] md:[&>dl]:justify-start" />
      </div>

      <ComposerActions>
        <Button href="/profile" fullWidth className={COMPOSER_ACTION_BUTTON}>
          See my submissions
          <ArrowRight size={20} aria-hidden="true" />
        </Button>
      </ComposerActions>
    </div>
  );
}
