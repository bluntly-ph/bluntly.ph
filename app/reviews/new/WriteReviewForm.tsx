"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import {
  ArrowRight,
  Check,
  CheckCircle,
  Equals,
  Image as ImageIcon,
  MagnifyingGlass,
  Link as LinkIcon,
  Plus,
  Star,
  X,
} from "@phosphor-icons/react/dist/ssr";
import type { Icon } from "@phosphor-icons/react";

import { ComposerHeader } from "@/components/reviews/ComposerHeader";
import {
  MAX_TITLE,
  blockerFor,
  buttonLabel,
  counterIsSatisfied,
  counterLabel,
} from "@/components/reviews/composer-gate-model";
import { MascotPrompt } from "@/components/reviews/MascotPrompt";
import { ProductStepDecor } from "@/components/reviews/ProductStepDecor";
import { PriceCaptureCard } from "@/components/reviews/PriceCaptureCard";
import { ReviewPreviewCard } from "@/components/reviews/ReviewPreviewCard";
import type { PanelUser } from "@/components/site/ProfileNavPanel";
import { Button } from "@/components/ui/Button";
import { prepareImageForUpload, usablePhoto } from "@/lib/image";

type Product = {
  id: string;
  canonical_name: string | null;
  category: string | null;
  /**
   * The product photo the catalogue already stores.
   *
   * QA-001: the picker drew a grey square for every result and never asked for
   * this, so a reviewer choosing between "Anker 737" and "Aukey 10000mAh" had
   * two identical blank tiles to tell them apart. `ProductOut` has served
   * `image_url` all along; only this type omitted it.
   */
  image_url: string | null;
};
type Verdict = "yes_absolutely" | "it_depends" | "hard_pass";

const VERDICTS: {
  value: Verdict;
  label: string;
  hint: string;
  ring: string;
  Icon: Icon;
}[] = [
  {
    value: "yes_absolutely",
    label: "Yes, absolutely!",
    hint: "You'd tell a friend to buy it.",
    ring: "var(--accent-success)",
    Icon: Check,
  },
  {
    value: "it_depends",
    label: "It depends",
    hint: "Right for some people, wrong for others.",
    ring: "var(--accent-star)",
    Icon: Equals,
  },
  {
    value: "hard_pass",
    label: "Hard pass",
    hint: "You'd tell a friend to save their money.",
    ring: "var(--accent-danger)",
    Icon: X,
  },
];

/**
 * The rating row is drawn as an arc: same-size stars whose vertical offset dips
 * away from the middle. Measured from "Reviewer Page - Step 3.1.png", where the
 * five 45x44 stars sit at y 373, 362, 357, 362, 373.
 */
const STAR_ARC = [16, 5, 0, 5, 16] as const;

/** Enforced in the API too (MAX_DISCUSSION_CHARS) — BUG-022. */
const MAX_DISCUSSION = 5000;

const lines = (s: string) =>
  s.split("\n").map((x) => x.trim()).filter(Boolean).slice(0, 10);

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
    blurb:
      "Boost your review's credibility by adding key information people want to know",
  },
  4: {
    title: "No product is for everybody",
    blurb:
      "At bluntly, we believe that there's no such thing as a perfect product",
  },
  5: {
    title: "Show, don't tell",
    blurb:
      "A photo of the actual product verifies your review and is required for earning eligibility.",
  },
  6: {
    title: "Final touch",
    blurb: "This is what people see first. Make it stand out!",
  },
};

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

  const patch = useCallback(
    (changes: Partial<Draft>) => setDraft((d) => ({ ...d, ...changes })),
    [],
  );

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

  return (
    <>
      <ComposerHeader user={user} onBack={back.run} backLabel={back.label} />

      {/* pb clears the bottom-anchored Continue (56px pill + 32px inset). */}
      <main className="mx-auto w-full max-w-[42rem] flex-1 px-4 pt-3 pb-[120px] sm:px-6">
        {phase === "done" ? (
          <DoneStep />
        ) : (
          <>
            <ResumeList drafts={resumable} onResume={resume} onDiscard={discard} />

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
                user={user}
                onChangeProduct={() => setPhase("product")}
                onDone={() => {
                  clearDraft(draftSlot(product));
                  setPhase("done");
                }}
              />
            ) : null}
          </>
        )}
      </main>
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
        {when ? (
          <p className="mt-1 text-[12px] text-[var(--text-secondary)]">Saved {when}.</p>
        ) : null}
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
 * Step 7's title field.
 *
 * Measured from "Reviewer Page - Step 7.png" at 390:
 *
 *   field        x16..373 (358 wide), y228..280 — 53 tall, white, 16px radius
 *   placeholder  "Your interesting title here...", 15px, 17px in from the
 *                left, ink-800 at ~.30 (darkest pixel 189 over white)
 *   counter      "0/30 characters", 11px, right-aligned to the field's edge
 *
 * There is no visible label — the frame shows placeholder text only — so the
 * real label is present and hidden rather than dropped: a placeholder is not
 * an accessible name and it disappears the moment you type.
 */
function TitleField({
  value,
  onChange,
}: {
  value: string;
  onChange: (next: string) => void;
}) {
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
        className={`h-[53px] w-full rounded-[var(--radius-md)] bg-[var(--surface-card)] px-[17px] ${CHIP_FACE} text-[15px] text-[var(--text-primary)] shadow-[var(--shadow-card)] outline-none placeholder:text-[rgba(32,32,32,0.3)] focus-visible:shadow-[var(--shadow-card),inset_0_0_0_1px_var(--accent-primary)]`}
      />
      <p className={`mt-2 text-right ${CHIP_FACE} text-[11px] text-[var(--text-secondary)]`}>
        {value.length}/{MAX_TITLE} characters
      </p>
    </div>
  );
}

/**
 * Step 6: one upload target, the whole card.
 *
 * Measured from "Reviewer Page - Step 6.png" / "6.1.png" at 390:
 *
 *   card    x16..373 (358 wide), y246..635 — 390 tall, white, 16px radius
 *   icon    52x44 at pure black, centred, top edge 100px into the card.
 *           Phosphor's Image at fill weight draws well inside its box, so
 *           that is size 64 — at 52 it renders 42x36
 *   line 1  "Tap to upload your product photo", 15px ink-800, y409
 *   line 2  "Use your own photo of the product", 13px, y434, and light:
 *           the darkest pixel is 197 over white, so ink-800 at ~.26
 *   skip    "Skip - I'll add a photo later", 14px ink-800, centred, 22px
 *           under the card
 *   6.1     the photo covers the card edge to edge, same rounding
 *
 * Continue is grey in 6 and orange in 6.1, so the photo gates the step and
 * Skip is the way past it.
 *
 * WHAT THIS DROPS, deliberately and worth flagging: the separate proof-of-
 * purchase upload. The frame has one upload, its blurb assigns verification
 * to it ("A photo of the actual product verifies your review and is required
 * for earning eligibility"), and step 7 draws that same photo on the public
 * review card — so it is the product photo, and the receipt field is not in
 * this flow. ReceiptField and the receipt_key plumbing are left intact and
 * unmounted rather than deleted, because the backend's earn_eligible gate
 * reads receipt_key and nothing else: following the frame here removes a
 * capability, and that is the owner's call to confirm, not one to make
 * quietly by deleting the code.
 */
function ProductPhotoCard({
  url,
  onChange,
  onSkip,
}: {
  url: string | null;
  onChange: (url: string | null) => void;
  onSkip: () => void;
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
        className="relative block h-[390px] w-full cursor-pointer overflow-hidden rounded-[var(--radius-md)] bg-[var(--surface-card)] shadow-[var(--shadow-card)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-primary)] disabled:cursor-wait"
      >
        {url ? (
          <Image src={url} alt="" fill sizes="358px" className="object-cover" />
        ) : (
          <span className="flex h-full flex-col items-center pt-[100px]">
            <ImageIcon
              size={64}
              weight="fill"
              aria-hidden="true"
              className="text-[var(--base-black)]"
            />
            <span className={`mt-[14px] ${CHIP_FACE} text-[15px] text-[var(--text-primary)]`}>
              {busy ? "Uploading…" : "Tap to upload your product photo"}
            </span>
            <span className={`mt-[6px] ${CHIP_FACE} text-[13px] text-[rgba(32,32,32,0.26)]`}>
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
        className={`mt-[22px] block w-full cursor-pointer text-center ${CHIP_FACE} text-[14px] text-[var(--text-primary)] underline-offset-4 hover:underline`}
      >
        Skip &ndash; I&apos;ll add a photo later
      </button>

      {error ? (
        <p role="alert" className="mt-3 text-center text-[13px] text-[var(--accent-danger)]">
          {error}
        </p>
      ) : null}
    </div>
  );
}

/**
 * The clouds behind step 3's stars.
 *
 * "Reviewer Page - Step 3.1.png" scatters outlined clouds across the whole
 * step. An autocorrelation over the band finds no repeat — they are placed by
 * hand, not tiled — so the layer is lifted from the frame the way the crowd
 * tile is: alpha = (242 - value) / 210, keeping only pixels under 232 so the
 * export's layout grid drops out, with the star row masked off. Composited
 * back over the page colour it reproduces the frame's clouds exactly.
 *
 * Frame coordinates, so MOBILE ONLY, like ProductStepDecor: the artwork spans
 * y247..757 of a 390-wide frame — down to the row above the Continue pill,
 * which starts at y759 — putting its top 205px below the header rule. There is no desktop frame for this step to place it against.
 */
function RatingStepDecor() {
  return (
    <span
      aria-hidden="true"
      className="pointer-events-none absolute -left-4 -right-4 -z-10 hidden h-[511px] select-none bg-[length:390px_511px] bg-top bg-no-repeat max-sm:block"
      style={{
        // The artwork starts 205px below the header rule in the frame. Measured
        // on the deployed page, the layer landed 92px lower than that; the
        // cluster tops now line up at 205 / 382 / 440 / 565 / 645 / 714.
        top: "-107px",
        backgroundImage: "url(/patterns/step3-clouds.png)",
      }}
    />
  );
}

/**
 * The crowd behind step 5's mascot.
 *
 * "Reviewer Page - Step 5.png" fills y238..419 edge to edge with a lattice of
 * outlined person glyphs. An autocorrelation over a clean 105x143 patch of it
 * puts the repeat at 41x31 (41x62 and 82x31 score no better, being two copies
 * of the same cell), with the seam at x31,y238.
 *
 * The tile in public/patterns is that cell, lifted straight out of the frame
 * rather than redrawn from an eyeballed circle-and-arc: each pixel's alpha is
 * (242 - value) / 210, i.e. how much ink-800 the export laid over the page
 * colour, with anything under 4% dropped to erase the faint layout grid the
 * export carries. Tiled back over #f2f2f2 it reproduces the band seamlessly.
 *
 * Purely decorative: hidden from assistive tech, and behind everything.
 */
function CrowdBand() {
  return (
    <span
      aria-hidden="true"
      className="pointer-events-none absolute -left-4 -right-4 top-0 -z-10 h-[182px] select-none bg-repeat sm:-left-6 sm:-right-6"
      style={{
        backgroundImage: "url(/patterns/crowd.png)",
        backgroundSize: "41px 31px",
      }}
    />
  );
}


/**
 * The frame's big write-it-here card, shared by step 1 and step 5.
 *
 * They are the same control in the pack — "Reviewer Page - Step 1.1.png" and
 * "Step 5.png" both draw a 358x231 white card at 12px radius with 20px of
 * padding, the placeholder "Write it *bluntly* here..." with the one word in
 * italics, 15px text on a 21px line, and a right-aligned counter under it.
 *
 * The counter is the step's gate written down. Empty, both read "30
 * characters remaining" in grey; satisfied, step 1 reads "Solid review!" and
 * step 5 "I'm sure someone will appreciate this", both in orange, and both
 * frames turn Continue from grey to orange at the same moment. So 30 is a
 * floor, not a limit.
 *
 * The card grows with the text: step 1.2's is well past 231px, while step
 * 5.1's four lines leave it at the minimum. `field-sizing: content` does that
 * without measuring scrollHeight in an effect, and where it is unsupported
 * the card stays at its minimum and scrolls.
 *
 * The italic word rules out the placeholder attribute, which is plain text
 * only, so it is drawn as an overlay — and the real label stays, hidden.
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
          className={`field-sizing-content block min-h-[231px] w-full resize-none rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-5 ${CHIP_FACE} text-[15px] leading-[21px] text-[var(--text-primary)] shadow-[var(--shadow-card)] outline-none focus-visible:shadow-[var(--shadow-card),inset_0_0_0_1px_var(--accent-primary)]`}
        />
        {value.length === 0 ? (
          <span
            aria-hidden="true"
            className={`pointer-events-none absolute left-5 top-5 ${CHIP_FACE} text-[15px] leading-[21px] text-[var(--text-muted)]`}
          >
            Write it <em>bluntly</em> here...
          </span>
        ) : null}
      </div>
      <p
        aria-live="polite"
        className={`mt-2 text-right ${CHIP_FACE} text-[11px] ${
          counterIsSatisfied(value)
            ? "text-[var(--accent-primary)]"
            : "text-[var(--base-gray-400)]"
        }`}
      >
        {counterLabel(value, satisfied)}
      </p>
    </div>
  );
}

/**
 * Step 1's product card: "Currently reviewing", the name, and a way out.
 *
 * Measured from "Reviewer Page - Step 1.1.png": card x16..373 y216..293,
 * white, 12px radius; the label 13px at rgb(55,113,200) — accent-trust to the
 * unit — the name 18px ink-800, and "Change" 16px in grey against the right
 * edge. This is the one place the pack names the product mid-flow, which is
 * why no other step draws it.
 */
function CurrentlyReviewingCard({
  name,
  onChange,
}: {
  name: string | null;
  onChange: () => void;
}) {
  return (
    <div className="flex items-end gap-3 rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-card)]">
      <div className="min-w-0 flex-1">
        <p className={`${CHIP_FACE} text-[13px] text-[var(--accent-trust)]`}>
          Currently reviewing
        </p>
        <p className={`mt-1 truncate ${CHIP_FACE} text-[18px] text-[var(--text-primary)]`}>
          {name ?? "your product"}
        </p>
      </div>
      <button
        type="button"
        onClick={onChange}
        className={`shrink-0 cursor-pointer ${CHIP_FACE} text-[16px] text-[var(--text-muted)] underline-offset-4 hover:text-[var(--text-primary)] hover:underline`}
      >
        Change
      </button>
    </div>
  );
}

/**
 * The chip shell, measured from "Reviewer Page - Step 4.png" at 390:
 *
 *   card        x16..373 (358 wide), fill #f2f2f2 — the page colour, told
 *               apart from the page by its shadow alone — 12px radius, 20px pad
 *   chip        52px tall, fill #f6f6f6, 12px radius, NO border, soft shadow
 *   row pitch   64px  (so a 12px vertical gap), ~10px horizontal gap
 *   plus        16px glyph at x54 — an 18px inset — then 10px to the label
 *   label       x80, a grotesque at ~15px, not Poppins: "Worth it!" is 58px
 *               wide with a 10px cap, where 13px Poppins renders it 67px wide
 *               with a 9px cap
 *
 * The live chips were 37px tall, white, and outlined in a hard grey hairline.
 */
const CHIP_FACE = "font-[family-name:var(--font-system)]";
const CHIP_SHELL =
  `inline-flex h-[52px] items-center gap-[10px] rounded-[var(--radius-sm)] ` +
  `bg-[rgb(246,246,246)] px-[18px] text-[15px] ` +
  `shadow-[0_4px_4px_0_var(--shadow-color-10)] ${CHIP_FACE}`;

/**
 * The plus in front of a chip's label.
 *
 * Every state is the same glyph at half opacity over the chip fill, which is
 * how the frame's exact values fall out: grey-400 at .5 over #f6f6f6 is the
 * measured rgb(193,193,193), success-600 is rgb(138,210,151), and danger is
 * rgb(231,123,142) — all three to the unit. Selection is carried by this
 * colour and by the label turning brand orange; the frame adds no border, and
 * the live chip's orange outline was not in it.
 */
function ChipPlus({ color }: { color: string }) {
  return <Plus size={16} aria-hidden="true" className="shrink-0 opacity-50" style={{ color }} />;
}

/**
 * Chips plus free text, over the same newline-joined string the draft and the
 * submit payload already use — so nothing downstream changes shape.
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
  const has = (phrase: string) =>
    chosen.some((c) => c.toLowerCase() === phrase.toLowerCase());

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
  const extras = chosen.filter(
    (c) => !suggestions.some((s) => s.toLowerCase() === c.toLowerCase()),
  );
  const accent =
    tone === "pro" ? "text-[var(--accent-trust)]" : "text-[var(--accent-danger)]";

  return (
    <div className="rounded-[var(--radius-sm)] bg-[var(--surface-app)] p-5 shadow-[var(--shadow-card)]">
      <p className={`text-[13px] font-semibold ${accent}`}>{label}</p>
      <p className={`mt-0.5 ${CHIP_FACE} text-[13px] text-[var(--text-secondary)]`}>
        {prompt}
      </p>

      <ul className="mt-3 flex flex-wrap gap-x-[10px] gap-y-3">
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

      {/* The frame draws this as one more chip — same 52px shell, same grey
          plus — that happens to accept typing, not as a bordered form input.
          A placeholder is not an accessible name and disappears on focus, so
          the real label is still there, just visually hidden. */}
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
          className="min-w-0 flex-1 bg-transparent outline-none placeholder:text-[var(--text-muted)]"
        />
      </div>
    </div>
  );
}

/* ----------------------------------------------------------------- product */

/**
 * A product's photo in the picker, or a neutral tile when there isn't one.
 *
 * Most of the catalogue has no image yet, so the tile stays — but it is now a
 * fallback rather than the only thing this component could draw.
 */
function ProductThumb({ product }: { product: Product }) {
  const src = usablePhoto(product.image_url);
  if (!src) {
    return (
      <span
        aria-hidden="true"
        className="h-9 w-9 shrink-0 rounded-[8px] bg-[var(--base-gray-200)]"
      />
    );
  }
  return (
    <span className="relative h-9 w-9 shrink-0 overflow-hidden rounded-[8px] bg-[var(--base-gray-200)]">
      <Image
        src={src}
        alt=""
        fill
        sizes="36px"
        className="object-cover"
      />
    </span>
  );
}

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
    // `relative` so the decorative rating cards can be positioned against this
    // step, and `isolate` so they are actually visible: they sit at -z-10, and
    // without a stacking context here that puts them behind the page's own
    // background rather than behind this step's content.
    <div className="relative isolate">
      <ProductStepDecor />
      {/* This screen's heading block is set like every other step's, which it
          was not: "Reviewer Page - Step 1.png" puts glyph tops at 89 / 111 /
          141, an eyebrow and a subtitle in the file's grotesque, and the
          heading in Poppins at 24/600 — 226px wide with 2px stems, where
          26px bold renders it 248px wide with 4px stems. */}
      <p className={`${CHIP_FACE} text-[13px] text-[var(--text-primary)]`}>
        Let&rsquo;s get started!
      </p>
      <h1 className="mt-[3px] text-[24px] font-semibold leading-[25px] text-[var(--accent-primary)]">
        What did you buy?
      </h1>
      <p className={`mt-[7px] ${CHIP_FACE} text-[13px] leading-[18px] text-[var(--text-secondary)]`}>
        Find the product. Your review will matter.
      </p>

      {/* x16..373 and 56 tall at y174, the page colour inside a hairline pill
          — not a raised white card, and with no magnifier in it. The glyph was
          this field's only decoration and the frame does not draw one. */}
      <div className="mt-[19px]">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="e.g Jisulife Fanlife 9"
          className={`h-[56px] w-full rounded-[var(--radius-pill)] bg-[var(--surface-app)] px-5 ${CHIP_FACE} text-[14px] text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)] outline-none placeholder:text-[var(--text-muted)] focus-visible:shadow-[0_0_0_2px_var(--accent-primary)]`}
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
              <ProductThumb product={p} />
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

      {/* The reference fills the space under the field with an empty state:
          a magnifier, "Find the product you bought", and the two-line hint,
          its block running y411..545 below the header.
          The composer never had it, which is why the page — and desktop in
          particular, where the column is only 672px of a much wider viewport —
          read as an empty grey void below the search box. */}
      {!searching ? (
        <div className="flex flex-col items-center pb-16 pt-[159px] text-center">
          <MagnifyingGlass size={40} className="text-[var(--text-muted)]" />
          <p className="mt-4 text-[16px] font-semibold text-[var(--text-primary)]">
            Find the product you bought
          </p>
          <p className="mt-1 max-w-[22rem] text-[14px] text-[var(--text-secondary)]">
            No need for the exact model.
            <br />
            Just type what you know
          </p>
        </div>
      ) : null}

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
  onDone: () => void;
}) {
  const [busy, setBusy] = useState(false);
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
        // The card stays open so the error is read where the action was taken.
        return;
      }
      setAskingPrice(false);
      onDone();
    } catch {
      setError("Couldn't reach the server. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      {/* Back lives in the header now, as a bare arrow — the frames draw no
          breadcrumb here. No progress bar either: measured across steps 2,
          3.1, 5 and 7, there are zero wide orange horizontal runs anywhere in
          the header band. The step count is the only progress the design shows.

          Type measured from "Reviewer Page - Step 2.png" at 390:
            step count  13px, ink-800 at full strength (darkest pixel 32, not
                        the muted grey this drew at 158)
            title       Poppins 20px / weight 500 — "Your verdict" is 120px
                        wide with 2px stems, where 22px bold renders it 137px
                        wide with 4px stems and twice the ink
            blurb       13px, text-secondary (darkest pixel 95 = ink-800 @ .7)
          Vertical rhythm, glyph tops measured from the header rule: step
          count 89, title 112, blurb 144 and 162 — an 18px line. The live page
          sat at 92/123/158/177 before these margins were cut.

          The count and the blurb are set in the file's grotesque, not Poppins:
          "Your unfiltered words. Make it count." is 212px wide in the frame
          and 233px in 13px Poppins, and the letterforms in a 3x crop are a
          different face entirely. The orange title stays Poppins. */}
      <p className={`${CHIP_FACE} text-[13px] text-[var(--text-primary)]`}>
        Step {step + 1} out of {STEPS.length}
      </p>

      <h1
        // Orange on every step: the reference draws each heading in the accent,
        // not just the ones with their own line underneath.
        className="mt-[6px] text-[length:var(--text-lg)] font-[number:var(--weight-medium)] leading-[21px] text-[var(--accent-primary)]"
      >
        {STEP_COPY[step]?.title ?? STEPS[step]}
      </h1>
      {STEP_COPY[step] ? (
        <p className={`mt-[10px] ${CHIP_FACE} text-[13px] leading-[18px] text-[var(--text-secondary)]`}>
          {STEP_COPY[step].blurb}
        </p>
      ) : null}

      <div className="mt-5">
        {step === 0 ? (
          <>
            <CurrentlyReviewingCard
              name={product.canonical_name}
              onChange={onChangeProduct}
            />
            <BluntlyTextarea
              label="Tell us your experience"
              value={draft.discussion}
              onChange={(discussion) =>
                patch({ discussion: discussion.slice(0, MAX_DISCUSSION) })
              }
              satisfied="Solid review!"
              autoFocus
              className="mt-4"
            />
          </>
        ) : null}

        {step === 1 ? (
          <div className="flex flex-col gap-3">
            {/* The references switch treatment here: step 2 and 2.1 draw the
                flat silhouette while nothing is chosen, and step 2.2 — the frame
                where a verdict HAS been picked and Bunbun asks why — draws the
                full illustration. So the mascot reacts to the answer. */}
            <MascotPrompt
              className="mb-2"
              variant={draft.verdict ? "detailed" : "simple"}
            >
              {draft.verdict
                ? "Woah, mind telling us why?"
                : "Would you recommend this to a friend?"}
            </MascotPrompt>
            {VERDICTS.map((v) => (
              <button
                key={v.value}
                type="button"
                onClick={() => patch({ verdict: v.value })}
                aria-pressed={draft.verdict === v.value}
                // As drawn: a white card with a soft drop shadow and no outline
                // at rest; the chosen one takes the verdict's own colour as a
                // ring, which is how step 2.2 shows the selection.
                className="flex items-center gap-3 rounded-[var(--radius-md)] bg-[var(--surface-card)] px-4 py-4 text-left shadow-[var(--shadow-card)] transition-shadow"
                style={
                  draft.verdict === v.value
                    ? { boxShadow: `inset 0 0 0 2px ${v.ring}` }
                    : undefined
                }
              >
                {/* The reference marks each choice with its own glyph, always in
                    that choice's colour rather than only once selected — it is
                    what makes the three readable at a glance. Decorative: the
                    label already names the verdict. */}
                <v.Icon
                  size={22}
                  aria-hidden="true"
                  className="shrink-0"
                  style={{ color: v.ring }}
                />
                {/* One line, as drawn. The hint that used to sit under each label
                    is gone: the reference shows the label alone, and the design
                    is the visual contract rather than an engineering preference.
                    `v.hint` still describes the option to assistive tech, so the
                    guidance is kept where it costs nothing visually. */}
                <span
                  className="text-[16px] font-medium"
                  style={{
                    color: draft.verdict === v.value ? v.ring : "var(--text-primary)",
                  }}
                >
                  {v.label}
                </span>
                <span className="sr-only">{v.hint}</span>
              </button>
            ))}
          </div>
        ) : null}

        {step === 2 ? (
          <div className="relative isolate">
            <RatingStepDecor />
            {/* An arc, not a flat row. Measured from the reference: five stars
                of the SAME size, 45x44, at a 60px pitch, with the middle one
                highest and the outer pair dropped 16px — 16, 5, 0, 5, 16.

                A Star glyph fills about 85% of its Phosphor box: the frame's
                middle star measures 46x44, which is size 53, and 53 + a 7px
                gap is the 60px pitch that was measured. At size 45 with a 15px
                gap the pitch was right and every star was 7px too small.

                "Reviewer Page - Step 3.1.png" puts the row at y315..374 below
                the header rule and its blurb's glyph top at 144, so the stars
                sit 171px under the blurb. The live page had 42. */}
            <div className="mt-[153px] flex items-start justify-center gap-[7px]">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  type="button"
                  onClick={() => patch({ rating: n })}
                  aria-label={`${n} star${n > 1 ? "s" : ""}`}
                  aria-pressed={draft.rating === n}
                  className="cursor-pointer focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-primary)]"
                  style={{ marginTop: STAR_ARC[n - 1] }}
                >
                  <Star
                    size={53}
                    weight="fill"
                    className={
                      n <= draft.rating
                        ? "text-[var(--accent-star)]"
                        : "text-[var(--base-gray-300)]"
                    }
                  />
                </button>
              ))}
            </div>
          </div>
        ) : null}

        {step === 3 ? (
          <div className="grid gap-5 sm:grid-cols-2">
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
            {/* "not" is red in the frame — rgb(216,0,39), the danger token to
                the unit — as well as bold and underlined. It was black here.
                Steps 5 and 5.1 both draw the silhouette; the illustration
                never appears on this step in the reference pack. */}
            <MascotPrompt variant="simple" className="pt-[59px]">
              Who should{" "}
              <strong className="font-bold text-[var(--accent-danger)] underline">
                not
              </strong>{" "}
              buy this?
            </MascotPrompt>

            {/* One textarea, not two single-line fields. The frame draws a
                single 358x231 card at y477 with 20px padding, and no "who is
                it right for" field at all — see AntiPersonaField. */}
            <BluntlyTextarea
              label="Who should not buy this?"
              value={draft.anti}
              onChange={(anti) => patch({ anti })}
              satisfied="I'm sure someone will appreciate this"
              className="mt-8"
            />
          </div>
        ) : null}

        {step === 5 ? (
          <ProductPhotoCard
            url={draft.photoUrl}
            onChange={(url) => patch({ photoUrl: url })}
            onSkip={() => patch({ step: step + 1 })}
          />
        ) : null}

        {step === 6 ? (
          <>
            <TitleField value={draft.title} onChange={(title) => patch({ title })} />
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
        busy={busy}
        error={error}
        onPriceChange={(price) => patch({ price })}
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
          moved into a live region instead of off the screen entirely. */}
      <div className="pointer-events-none fixed inset-x-0 bottom-0 z-20 pb-8">
        <div className="mx-auto w-full max-w-[42rem] px-4 sm:px-6">
          <Button
            type="button"
            onClick={isLast ? () => setAskingPrice(true) : () => patch({ step: step + 1 })}
            disabled={Boolean(blocker) || busy}
            fullWidth
            className="pointer-events-auto"
          >
            {buttonLabel(step, STEPS.length, busy)}
            {busy ? null : <ArrowRight size={18} weight="bold" aria-hidden="true" />}
          </Button>
        </div>
      </div>
      <p role="status" className="sr-only">
        {blocker ?? "Saved as you type."}
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ shared */

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
