"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import {
  ArrowRight,
  AsteriskSimple,
  Check,
  Cloud,
  DotOutline,
  Image as ImageIcon,
  LinkSimple,
  MagnifyingGlass,
  NumberFive,
  NumberFour,
  NumberOne,
  NumberThree,
  NumberTwo,
  Plus,
  SealCheck,
  Star,
  X,
} from "@phosphor-icons/react/dist/ssr";

import { COMPOSER_FOCUS_RING, COMPOSER_HEADING, COMPOSER_HINT } from "@/components/reviews/composer-styles";
import { ComposerGrid, ComposerHeader } from "@/components/reviews/ComposerHeader";
import { CurrentlyReviewingCard } from "@/components/reviews/CurrentlyReviewingCard";
import { LatestStats } from "@/components/reviews/LatestStats";
import { ReviewPreviewCard } from "@/components/reviews/ReviewPreviewCard";
import {
  DONE_CARDS,
  STAR_CORAL,
  STAR_GREEN,
  STAR_YELLOW,
  TiltedRatingCards,
  fadedStar,
  starRow,
  type TiltedCard,
} from "@/components/reviews/TiltedRatingCards";
import type { PanelUser } from "@/components/site/ProfileNavPanel";
import { Button } from "@/components/ui/Button";
import { prepareImageForUpload } from "@/lib/image";

import {
  DIMENSION_PROMPT,
  MAX_SELLER_COMMENT,
  MAX_SELLER_PHOTOS,
  MAX_SELLER_TITLE,
  MIN_SELLER_PROSE,
  PLATFORM_LABEL,
  contentBlocker,
  emptySellerDraft,
  missingDimension,
  ratingPrompt,
  sellerInitials,
  toSellerReviewPayload,
  type SellerDraft,
  type SellerPlatform,
  type SellerReviewPayload,
} from "./seller-model";

/**
 * The seller-review composer (FR-4), built to the "Seller Review" frames, read
 * from Figma 2026-09-15:
 *
 *   find    Step 1 (4611:9344, empty) and Step 1 with results (4627:9403)
 *   rate    Step 2 (4627:9613) and Step 2.6 (4652:12139, everything chosen)
 *   write   Step 3 (4645:10125) and Step 3.3 (4652:12635, filled)
 *   done    All done (4652:12914)
 *
 * The progress line under the bar is the frames' own: grey on find, 39 of
 * 390px orange on rate, 312px on write, all green on done.
 *
 * Seller reviews publish immediately — they carry no affiliate link and earn
 * nothing, so they skip the product-review moderation gate (DEVIATIONS §37);
 * a moderator can remove one afterwards. That is why this done screen can say
 * "now live" when the product composer's cannot.
 *
 * INTENTIONAL PRODUCT DIFFERENCES:
 *  - The headline restores a dropped word: the frame reads "Who are rating
 *    today?". The empty state speaks of a seller; the frame kept the product
 *    composer's "Find the product you bought / No need for the exact model".
 *  - A result shows the marketplace where the frame shows "39 questions
 *    answered" (no answered-question count is served) and the store's
 *    initials where it shows a logo (stores carry none).
 *  - "Can't find seller? Paste Shopee link here" opens "Add a seller" with the
 *    link filled in and the marketplace read from the link's domain. A link
 *    alone cannot name a store without fetching the marketplace page, which
 *    this product does not do. A search with no results also offers to add
 *    the typed name, so a buyer with no link is not stranded.
 *  - The stats are the reviewer's real dashboard figures (see LatestStats).
 *  - "Make it pop" lines up with the other write-step headings at 28px; the
 *    frame alone sets it 4px further left.
 */

export type PickedSeller = {
  id: string;
  display_name: string;
  platform: SellerPlatform;
  claim_status: string;
  review_count: number;
};

type Stage = "find" | "rate" | "write" | "done";

const PROGRESS: Record<Stage, number> = { find: 0, rate: 39 / 390, write: 312 / 390, done: 1 };

const HEADING = COMPOSER_HEADING;
const HINT = COMPOSER_HINT;
const FOCUS_RING = COMPOSER_FOCUS_RING;
/** The white 53px field at radius 16 the write step draws; the 1px border takes an orange line once filled. */
const FIELD =
  "w-full rounded-[16px] border bg-[var(--surface-card)] px-[15px] text-[14px] text-[var(--text-primary)] shadow-[var(--shadow-card)] outline-none placeholder:text-[rgba(32,32,32,0.3)] focus-visible:border-[var(--accent-primary)]";

export function RateSellerForm({
  user,
  initialSeller,
}: {
  user: PanelUser;
  initialSeller: PickedSeller | null;
}) {
  const router = useRouter();
  const [seller, setSeller] = useState<PickedSeller | null>(initialSeller);
  const [stage, setStage] = useState<Stage>(initialSeller ? "rate" : "find");
  const [draft, setDraft] = useState<SellerDraft>(emptySellerDraft);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const patch = (change: Partial<SellerDraft>) => setDraft((d) => ({ ...d, ...change }));

  function go(next: Stage) {
    setError(null);
    setStage(next);
    window.scrollTo({ top: 0 });
  }

  function pick(next: PickedSeller) {
    setSeller(next);
    go("rate");
  }

  async function submit() {
    if (!seller || busy) return;
    let payload: SellerReviewPayload;
    try {
      payload = toSellerReviewPayload(draft);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something is still missing.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/bff/api/v1/sellers/${seller.id}/reviews`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const p = (await res.json().catch(() => ({}))) as { detail?: string };
        setError(p.detail ?? "Couldn't post your seller review.");
        return;
      }
      go("done");
    } catch {
      setError("Couldn't reach the server. Try again.");
    } finally {
      setBusy(false);
    }
  }

  const missing = missingDimension(draft);
  const blocker =
    stage === "rate"
      ? missing
        ? DIMENSION_PROMPT[missing]
        : null
      : stage === "write"
        ? contentBlocker(draft)
        : null;

  const back =
    stage === "find"
      ? () => router.back()
      : stage === "rate"
        ? () => go("find")
        : stage === "write"
          ? () => go("rate")
          : seller
            ? () => router.push(`/sellers/${seller.id}`)
            : undefined;

  return (
    <>
      <ComposerHeader
        user={user}
        onBack={back}
        backLabel={
          stage === "write"
            ? "Back to the ratings"
            : stage === "rate"
              ? "Choose another seller"
              : stage === "done"
                ? "Go to the seller"
                : "Leave"
        }
        progress={PROGRESS[stage]}
      />
      <ComposerGrid />
      {/* pb clears the bottom-anchored pill (56px + 32px inset) and the link field. */}
      <main className="mx-auto w-full max-w-[42rem] flex-1 px-4 pb-[120px] pt-4 sm:px-6">
        {stage === "find" ? <FindSeller onPick={pick} /> : null}
        {stage === "rate" && seller ? (
          <RateStep seller={seller} draft={draft} patch={patch} onChangeSeller={() => go("find")} />
        ) : null}
        {stage === "write" ? (
          <WriteStep
            draft={draft}
            patch={patch}
            addPhoto={(url) =>
              setDraft((d) => ({ ...d, photoUrls: [...d.photoUrls, url].slice(0, MAX_SELLER_PHOTOS) }))
            }
            removePhoto={(url) =>
              setDraft((d) => ({ ...d, photoUrls: d.photoUrls.filter((u) => u !== url) }))
            }
          />
        ) : null}
        {stage === "done" && seller ? <DoneStep seller={seller} draft={draft} user={user} /> : null}
      </main>

      {/* Pinned to the viewport, as every frame draws it: y757 in an 844 device
          even on the 1192px rate frame. */}
      {stage === "rate" || stage === "write" ? (
        <div className="pointer-events-none fixed inset-x-0 bottom-0 z-20 pb-8">
          <div className="mx-auto w-full max-w-[42rem] px-4 sm:px-6">
            {error ? (
              <p
                role="alert"
                className="pointer-events-auto mb-2 rounded-[12px] bg-[var(--surface-card)] px-4 py-3 text-[12px] leading-[18px] text-[var(--accent-danger)] shadow-[var(--shadow-card)]"
              >
                {error}
              </p>
            ) : null}
            <Button
              type="button"
              onClick={stage === "rate" ? () => go("write") : submit}
              disabled={Boolean(blocker) || busy}
              fullWidth
              className="pointer-events-auto gap-1"
            >
              {stage === "rate" ? "Continue" : busy ? "Posting…" : "Submit"}
              {busy ? null : <ArrowRight size={20} aria-hidden="true" />}
            </Button>
          </div>
        </div>
      ) : null}
      <p role="status" className="sr-only">
        {blocker ?? ""}
      </p>
    </>
  );
}

/* ------------------------------------------------------------------- find */

/**
 * Step 1's cards: three sliding in from the left at mid-height and three from
 * the bottom right, faces at 70%. Measured below the bar (frame y114).
 */
const FIND_CARDS: TiltedCard[] = [
  { x: -133, top: 315, tilt: 5, faded: true, stars: starRow(5, STAR_GREEN) },
  { x: -116, top: 261, tilt: 5, faded: true, stars: starRow(4, STAR_GREEN) },
  { x: -100, top: 206, tilt: 5, faded: true, stars: starRow(2, fadedStar(STAR_CORAL)) },
  { x: 363, bottom: -8, tilt: -5, faded: true, anchorRight: true, starsStart: true, stars: starRow(5, STAR_GREEN) },
  { x: 347, bottom: 46, tilt: -5, faded: true, anchorRight: true, starsStart: true, stars: starRow(4, STAR_GREEN) },
  { x: 330, bottom: 101, tilt: -5, faded: true, anchorRight: true, starsStart: true, stars: starRow(3, fadedStar(STAR_YELLOW)) },
];

/**
 * Figma 4611:9344 / 4627:9403: "Let's get started!" in 12px Regular, the
 * question 10px lower in 20px Medium brand orange, the blurb 10px lower in 12px
 * Light at 70%; a 56px pill field with a 1px #323232 outline, the query 24px in
 * at 16px Regular and 0.8px tracking. Results: "N results found" 25px under the
 * field, a hairline 17px lower, then 112px rows.
 */
function FindSeller({ onPick }: { onPick: (seller: PickedSeller) => void }) {
  const inputId = useId();
  const linkId = useId();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<PickedSeller[]>([]);
  const [link, setLink] = useState("");
  const [adding, setAdding] = useState(false);

  const query = q.trim();
  const searching = query.length >= 2;

  useEffect(() => {
    if (!searching) return;
    const t = setTimeout(async () => {
      try {
        const res = await fetch(`/api/bff/api/v1/sellers?q=${encodeURIComponent(query)}&limit=8`);
        setResults(res.ok ? ((await res.json()) as PickedSeller[]) : []);
      } catch {
        setResults([]);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [query, searching]);

  // Derived, not stored: results from an earlier query must not outlive a
  // query that no longer qualifies (react-hooks/set-state-in-effect).
  const visible = searching ? results : null;

  return (
    <div>
      {visible === null && !adding ? (
        <TiltedRatingCards cards={FIND_CARDS} className="fixed inset-x-0 bottom-0 top-[72px] -z-10 hidden max-sm:block" />
      ) : null}

      <p className="text-[12px] leading-none text-[var(--text-primary)]">Let&rsquo;s get started!</p>
      <h1 className="mt-2.5 text-[20px] font-medium leading-none text-[var(--accent-primary)]">
        Who are you rating today?
      </h1>
      <p className="mt-[7px] text-[12px] font-light leading-[18px] text-[rgba(32,32,32,0.7)]">
        Find the seller. Help people buy from the right place
      </p>

      <label htmlFor={inputId} className="sr-only">
        Store name
      </label>
      <input
        id={inputId}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        autoComplete="off"
        placeholder="e.g Jisulife Official Store"
        className="mt-[19px] h-14 w-full rounded-[var(--radius-pill)] border border-[var(--base-gray-600)] bg-[var(--surface-app)] px-6 text-[16px] tracking-[0.8px] text-[var(--text-primary)] outline-none placeholder:text-[rgba(32,32,32,0.4)] focus-visible:border-[var(--accent-primary)]"
      />

      {adding ? (
        <AddSellerForm
          initialName={query}
          initialLink={link.trim()}
          onAdded={onPick}
          onCancel={() => setAdding(false)}
        />
      ) : visible === null ? (
        // The empty state, 174px under the field: a 64px MagnifyingGlass in a
        // 2px line, a line of 16px Regular at 0.8px tracking, and the hint in
        // 12px Light at 70% on 18px lines, 180px wide.
        <div className="flex flex-col items-center pt-[174px] text-center">
          <MagnifyingGlass size={64} weight="thin" aria-hidden="true" className="text-[var(--base-black)]" />
          <p className="mt-4 text-[16px] leading-none tracking-[0.8px] text-[var(--text-primary)]">
            Find the seller you bought from
          </p>
          <p className="mt-[9px] text-[12px] font-light leading-[1.5] text-[rgba(32,32,32,0.7)]">
            No need for the exact store name.
            <br />
            Just type what you know
          </p>
        </div>
      ) : (
        <>
          <p aria-live="polite" className="mt-[25px] text-[12px] leading-none text-[var(--text-primary)]">
            {visible.length} {visible.length === 1 ? "result" : "results"} found
          </p>
          {visible.length > 0 ? (
            <ul className="-mx-4 mt-[17px] border-t border-[var(--line-hairline-10)] sm:-mx-6">
              {visible.map((s) => (
                <li key={s.id} className="border-b border-[var(--line-hairline-10)]">
                  <SellerPick seller={s} onPick={onPick} />
                </li>
              ))}
            </ul>
          ) : (
            <button
              type="button"
              onClick={() => setAdding(true)}
              className={`mt-5 cursor-pointer text-[14px] leading-none text-[var(--accent-primary)] underline-offset-4 hover:underline ${FOCUS_RING}`}
            >
              Add &ldquo;{query}&rdquo; as a new seller
            </button>
          )}
        </>
      )}

      {/* Figma "LinkField" (6943:925) 35px above the bottom edge: 52px, white at
          30% with a 0 4px 4px shadow at 10%, radius 12; a 20px LinkSimple 8px
          before 14px Regular at 30% ink. It is the paste field itself. */}
      {adding ? null : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (link.trim()) setAdding(true);
          }}
          className="fixed inset-x-0 bottom-[35px] z-20 px-4 sm:px-6"
        >
          <div className="mx-auto flex h-[52px] w-full max-w-[42rem] items-center gap-2 rounded-[12px] bg-[rgba(255,255,255,0.3)] px-4 shadow-[0_4px_4px_0_var(--shadow-color-10)] backdrop-blur-sm">
            <LinkSimple size={20} weight="light" aria-hidden="true" className="shrink-0 text-[var(--base-gray-400)]" />
            <label className="sr-only" htmlFor={linkId}>
              Can&rsquo;t find the seller? Paste the store&rsquo;s Shopee or Lazada link
            </label>
            <input
              id={linkId}
              value={link}
              onChange={(e) => setLink(e.target.value)}
              inputMode="url"
              autoComplete="off"
              placeholder="Can’t find seller? Paste Shopee link here"
              className="min-w-0 flex-1 bg-transparent text-[14px] leading-none text-[var(--text-primary)] outline-none placeholder:text-[rgba(32,32,32,0.3)]"
            />
            {link.trim() ? (
              <button
                type="submit"
                className="shrink-0 cursor-pointer rounded-[20px] bg-[var(--accent-primary)] px-3 py-2 text-[12px] font-light leading-none text-[var(--text-on-brand)]"
              >
                Add seller
              </button>
            ) : null}
          </div>
        </form>
      )}
    </div>
  );
}

/**
 * A result row, Figma 4627:9403: an 80px white disc 16px in, and 12px after it
 * the claim line (a 16px SealCheck and 12px Regular, at 70%), the store 2px
 * under it in 16px SemiBold, the counts 16px lower in 12px Light split by a
 * 12px DotOutline. 16px above and below; a hairline between rows.
 */
function SellerPick({ seller, onPick }: { seller: PickedSeller; onPick: (seller: PickedSeller) => void }) {
  const claimed = seller.claim_status === "claimed";
  const count = seller.review_count;
  return (
    <button
      type="button"
      onClick={() => onPick(seller)}
      className="flex w-full cursor-pointer items-start gap-3 px-4 pb-4 pt-[15px] text-left text-[var(--text-primary)] hover:bg-[var(--line-hairline-10)] focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--accent-primary)] sm:px-6"
    >
      <span
        aria-hidden="true"
        className="grid h-20 w-20 shrink-0 place-items-center rounded-full bg-[var(--surface-card)] text-[24px] text-[var(--base-gray-400)]"
      >
        {sellerInitials(seller.display_name)}
      </span>
      <span className="min-w-0 flex-1 pt-1">
        <span className="flex h-4 items-center gap-1 text-[12px] leading-none text-[rgba(32,32,32,0.7)]">
          {claimed ? <SealCheck size={16} aria-hidden="true" /> : null}
          {claimed ? "Claimed Profile" : "Unclaimed Profile"}
        </span>
        <span className="mt-0.5 block truncate text-[16px] font-semibold leading-none">{seller.display_name}</span>
        <span className="mt-4 flex items-center gap-1 text-[12px] font-light leading-none">
          {count} {count === 1 ? "review" : "reviews"}
          <DotOutline size={12} aria-hidden="true" className="shrink-0 text-[var(--base-gray-400)]" />
          {PLATFORM_LABEL[seller.platform]}
        </span>
      </span>
    </button>
  );
}

/** The marketplace named by a pasted link's own domain, or nothing. */
function platformFromLink(link: string): SellerPlatform | null {
  let host: string;
  try {
    host = new URL(link).hostname.toLowerCase();
  } catch {
    return null;
  }
  for (const key of ["shopee", "lazada", "amazon"] as const) {
    if (host.startsWith(`${key}.`) || host.includes(`.${key}.`)) return key;
  }
  return null;
}

function FieldHeading({
  htmlFor,
  hintId,
  title,
  hint,
  className = "",
}: {
  htmlFor: string;
  hintId: string;
  title: string;
  hint: string;
  className?: string;
}) {
  return (
    <div className={className}>
      <label htmlFor={htmlFor} className={`block ${HEADING}`}>
        {title}
      </label>
      <p id={hintId} className={HINT}>
        {hint}
      </p>
    </div>
  );
}

/**
 * No frame draws this form (see the docblock at the top). It is built from the
 * write step's parts: 14px Medium headings over 12px Light hints, 53px white
 * fields at radius 16, and the marketplace as small pills — Button/Pill Small,
 * 32px at radius 20 in 12px Light.
 *
 * The API matches by name and marketplace, so adding a store that already
 * exists returns that store.
 */
function AddSellerForm({
  initialName,
  initialLink,
  onAdded,
  onCancel,
}: {
  initialName: string;
  initialLink: string;
  onAdded: (seller: PickedSeller) => void;
  onCancel: () => void;
}) {
  const nameId = useId();
  const nameHint = useId();
  const linkId = useId();
  const linkHint = useId();
  const [name, setName] = useState(initialName);
  const [platform, setPlatform] = useState<SellerPlatform>(platformFromLink(initialLink) ?? "shopee");
  const [link, setLink] = useState(initialLink);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/bff/api/v1/sellers", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          display_name: name.trim(),
          platform,
          store_url: link.trim() || null,
        }),
      });
      if (!res.ok) {
        const p = (await res.json().catch(() => ({}))) as { detail?: string };
        setError(p.detail ?? "Couldn't add that seller.");
        return;
      }
      onAdded((await res.json()) as PickedSeller);
    } catch {
      setError("Couldn't reach the server.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={add} className="mt-9">
      <FieldHeading
        htmlFor={nameId}
        hintId={nameHint}
        title="Add a seller"
        hint="The store’s name, as the marketplace shows it"
      />
      <input
        id={nameId}
        aria-describedby={nameHint}
        value={name}
        onChange={(e) => setName(e.target.value.slice(0, 160))}
        className={`mt-[18px] h-[53px] ${FIELD} ${name.trim() ? "border-[rgba(239,88,33,0.8)]" : "border-transparent"}`}
      />

      <fieldset className="mt-9 min-w-0">
        <legend className={HEADING}>Marketplace</legend>
        <div className="mt-[18px] flex flex-wrap gap-2">
          {(Object.keys(PLATFORM_LABEL) as SellerPlatform[]).map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => setPlatform(key)}
              aria-pressed={platform === key}
              className={`h-8 cursor-pointer rounded-[20px] px-4 text-[12px] font-light leading-none ${FOCUS_RING} ${
                platform === key
                  ? "bg-[var(--accent-primary)] text-[var(--text-on-brand)]"
                  : "bg-[var(--surface-card)] text-[var(--text-primary)] shadow-[var(--shadow-card)]"
              }`}
            >
              {PLATFORM_LABEL[key]}
            </button>
          ))}
        </div>
      </fieldset>

      <FieldHeading
        htmlFor={linkId}
        hintId={linkHint}
        title="Store link"
        hint="Optional. The store’s page, not a product’s"
        className="mt-9"
      />
      <input
        id={linkId}
        aria-describedby={linkHint}
        value={link}
        onChange={(e) => setLink(e.target.value)}
        inputMode="url"
        placeholder="Paste the store’s link"
        className={`mt-[18px] h-[53px] ${FIELD} border-transparent`}
      />

      {error ? (
        <p role="alert" className="mt-4 text-[12px] leading-[18px] text-[var(--accent-danger)]">
          {error}
        </p>
      ) : null}
      <div className="mt-8 flex items-center gap-6">
        <Button type="submit" disabled={!name.trim() || busy} className="gap-1">
          {busy ? "Adding…" : "Add seller"}
          {busy ? null : <ArrowRight size={20} aria-hidden="true" />}
        </Button>
        <button
          type="button"
          onClick={onCancel}
          className={`cursor-pointer text-[14px] leading-none text-[rgba(32,32,32,0.3)] hover:text-[var(--text-primary)] ${FOCUS_RING}`}
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

/* ------------------------------------------------------------------- rate */

/**
 * The clouds behind the stars, Figma 4627:9613: eleven Icon/Cloud glyphs, 24 to
 * 64px, several turned 180deg, in a 1px line at 20% ink. Frame coordinates,
 * measured below the bar. Step 2.6 draws the same clouds in the rating green,
 * so they take it once a star rating is chosen.
 */
const CLOUDS: { left: number; top: number; size: number; flip?: boolean }[] = [
  { left: 35, top: -8, size: 32 },
  { left: 9, top: 243, size: 32 },
  { left: 41, top: 218, size: 52 },
  { left: 73, top: -46, size: 64 },
  { left: 288, top: 51, size: 64, flip: true },
  { left: 342, top: 138, size: 32, flip: true },
  { left: 352, top: -8, size: 32, flip: true },
  { left: 107, top: 227, size: 24, flip: true },
  { left: 254, top: 361, size: 32, flip: true },
  { left: 202, top: 316, size: 52, flip: true },
  { left: 164, top: 401, size: 24 },
];

/**
 * Figma 4627:9613 / 4652:12139: the reviewing card; "How was the seller?" 47px
 * under it in 20px Medium brand orange, centred; five 40px stars 8px apart 31px
 * lower; the two recommend cards 32px lower, 8px apart; and 56px lower the white
 * sheet at radius 32 holding the four dimensions, 36px in from its top and 28px
 * from its sides.
 */
function RateStep({
  seller,
  draft,
  patch,
  onChangeSeller,
}: {
  seller: PickedSeller;
  draft: SellerDraft;
  patch: (change: Partial<SellerDraft>) => void;
  onChangeSeller: () => void;
}) {
  const rated = draft.overall !== null;
  return (
    <div className="relative">
      <span aria-hidden="true" className="pointer-events-none absolute -left-4 -top-4 -z-10 hidden select-none max-sm:block">
        {CLOUDS.map((c, i) => (
          <Cloud
            key={i}
            size={c.size}
            weight="thin"
            className={`absolute ${rated ? "text-[var(--semantic-success-500)]" : "text-[rgba(32,32,32,0.2)]"} ${
              c.flip ? "rotate-180" : ""
            }`}
            style={{ left: c.left, top: c.top }}
          />
        ))}
      </span>

      <CurrentlyReviewingCard name={seller.display_name} onChange={onChangeSeller} />

      <h1 className="mt-[47px] text-center text-[20px] font-medium leading-none text-[var(--accent-primary)]">
        How was the seller?
      </h1>
      <div className="mt-[31px] flex justify-center gap-2">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            onClick={() => patch({ overall: n })}
            aria-label={`${n} star${n > 1 ? "s" : ""}`}
            aria-pressed={draft.overall === n}
            className={`grid h-10 w-10 cursor-pointer place-items-center rounded-[6px] ${FOCUS_RING}`}
          >
            <Star
              size={40}
              weight="fill"
              aria-hidden="true"
              className={
                draft.overall !== null && n <= draft.overall
                  ? "text-[var(--semantic-success-500)]"
                  : "text-[var(--base-gray-400)]"
              }
            />
          </button>
        ))}
      </div>

      <div className="mt-8 flex flex-col gap-2">
        <ChoiceCard tone="yes" value={draft.recommend} choice full onPick={(recommend) => patch({ recommend })}>
          I recommend this seller
        </ChoiceCard>
        <ChoiceCard tone="no" value={draft.recommend} choice={false} full onPick={(recommend) => patch({ recommend })}>
          I don&rsquo;t recommend this seller
        </ChoiceCard>
      </div>

      {/* Run to the bottom of the page: the main column's bottom padding is
          taken back into the sheet, which keeps enough of its own to clear the
          pinned pill. */}
      <section className="-mx-4 -mb-[120px] mt-14 rounded-t-[32px] bg-[var(--surface-card)] px-7 pb-[120px] pt-9 sm:-mx-6 sm:px-8">
        <GradeQuestion
          title="Customer Service Responsiveness"
          hint="How was their response to your inquiries?"
          value={draft.service}
          onPick={(service) => patch({ service })}
        />
        <GradeQuestion
          title="Packaging Quality"
          hint="How well did they pack your order?"
          value={draft.packaging}
          onPick={(packaging) => patch({ packaging })}
          className="mt-[30px]"
        />
        <BinaryQuestion
          title="Ad Accuracy"
          hint="Did what arrived match the listing?"
          yes="Yes, accurate!"
          no="Not the same"
          value={draft.accuracy}
          onPick={(accuracy) => patch({ accuracy })}
          className="mt-[30px]"
        />
        <BinaryQuestion
          title="Order completeness"
          hint="Did you get exactly what you ordered?"
          yes="Exact order"
          no="Missing item"
          value={draft.completeness}
          onPick={(completeness) => patch({ completeness })}
          className="mt-7"
        />
      </section>
    </div>
  );
}

/**
 * A yes/no card, Figma 4627:9613: 53px white at radius 16 with the card
 * shadow, a 20px Check (green) or X (red) 16px in and 16px Regular... 14px
 * Regular 8px after it; the binary pairs hug their label, 12px apart. Step 2.6:
 * the chosen card takes a 1px orange line at 80%, the other drops to 60%.
 */
function ChoiceCard({
  tone,
  value,
  choice,
  full = false,
  onPick,
  children,
}: {
  tone: "yes" | "no";
  value: boolean | null;
  choice: boolean;
  full?: boolean;
  onPick: (choice: boolean) => void;
  children: React.ReactNode;
}) {
  const Icon = tone === "yes" ? Check : X;
  const selected = value === choice;
  const dimmed = value !== null && !selected;
  return (
    <button
      type="button"
      onClick={() => onPick(choice)}
      aria-pressed={selected}
      className={`flex h-[53px] cursor-pointer items-center gap-2 rounded-[16px] border bg-[var(--surface-card)] px-[15px] text-left text-[14px] leading-none text-[var(--text-primary)] shadow-[var(--shadow-card)] transition-opacity ${FOCUS_RING} ${
        selected ? "border-[rgba(239,88,33,0.8)]" : "border-transparent"
      } ${dimmed ? "opacity-60" : ""} ${full ? "w-full" : ""}`}
    >
      <Icon
        size={20}
        weight="bold"
        aria-hidden="true"
        className={`shrink-0 ${tone === "yes" ? "text-[var(--accent-success)]" : "text-[var(--accent-danger)]"}`}
      />
      {children}
    </button>
  );
}

const NUMERALS = [NumberOne, NumberTwo, NumberThree, NumberFour, NumberFive] as const;

/**
 * Figma 4627:9613: the dimension in 14px Medium, its hint 7px under it in 12px
 * Light at 70%, and 12px lower five 52px discs 12px apart, in the page colour
 * under a 0 4px 2px shadow at 10%, each carrying a 20px Phosphor numeral in a
 * 2px line. Chosen (2.6): brand orange with the numeral in the page colour.
 */
function GradeQuestion({
  title,
  hint,
  value,
  onPick,
  className = "",
}: {
  title: string;
  hint: string;
  value: number | null;
  onPick: (grade: number) => void;
  className?: string;
}) {
  const hintId = useId();
  return (
    <fieldset aria-describedby={hintId} className={`min-w-0 ${className}`}>
      <legend className={HEADING}>{title}</legend>
      <p id={hintId} className={HINT}>
        {hint}
      </p>
      <div className="mt-3 flex flex-wrap gap-3 drop-shadow-[0_4px_2px_rgba(0,0,0,0.1)]">
        {NUMERALS.map((Numeral, i) => {
          const n = i + 1;
          const chosen = value === n;
          return (
            <button
              key={n}
              type="button"
              onClick={() => onPick(n)}
              aria-pressed={chosen}
              aria-label={`${n} out of 5`}
              className={`grid h-[52px] w-[52px] cursor-pointer place-items-center rounded-full transition-colors ${FOCUS_RING} ${
                chosen
                  ? "bg-[var(--accent-primary)] text-[var(--surface-app)]"
                  : "bg-[var(--surface-app)] text-[var(--text-primary)]"
              }`}
            >
              <Numeral size={20} weight="bold" aria-hidden="true" />
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

function BinaryQuestion({
  title,
  hint,
  yes,
  no,
  value,
  onPick,
  className = "",
}: {
  title: string;
  hint: string;
  yes: string;
  no: string;
  value: boolean | null;
  onPick: (answer: boolean) => void;
  className?: string;
}) {
  const hintId = useId();
  return (
    <fieldset aria-describedby={hintId} className={`min-w-0 ${className}`}>
      <legend className={HEADING}>{title}</legend>
      <p id={hintId} className={HINT}>
        {hint}
      </p>
      <div className="mt-[18px] flex flex-wrap gap-3">
        <ChoiceCard tone="yes" value={value} choice onPick={onPick}>
          {yes}
        </ChoiceCard>
        <ChoiceCard tone="no" value={value} choice={false} onPick={onPick}>
          {no}
        </ChoiceCard>
      </div>
    </fieldset>
  );
}

/* ------------------------------------------------------------------ write */

/**
 * The three cards tumbling in over step 3, Figma 4645:10125: a 140px square
 * and two 185x95 cards, all turned -10deg with full faces, starting under the
 * bar. Frame coordinates below the bar.
 */
const WRITE_CARDS: TiltedCard[] = [
  { x: 118, top: -46, w: 140, h: 140, tilt: -10, stars: starRow(5, STAR_GREEN) },
  { x: -76, top: 30, tilt: -10, stars: starRow(3, STAR_YELLOW) },
  {
    x: 275,
    top: -32,
    tilt: -10,
    anchorRight: true,
    stars: [STAR_CORAL, STAR_CORAL, STAR_GREEN, STAR_GREEN, STAR_GREEN],
  },
];

/**
 * Figma 4645:10125 / 4652:12635: the rating prompt card 84px under the bar's
 * content line — 80px white at radius 12, a 40px green AsteriskSimple disc 20px
 * in, the prompt 17px after it in 14px Regular on 21px lines — then 32px lower
 * the white sheet: headings 36px apart, each 14px Medium over a 12px Light hint,
 * fields 18px under the hint, counters 4px under the field in 10px Light.
 */
function WriteStep({
  draft,
  patch,
  addPhoto,
  removePhoto,
}: {
  draft: SellerDraft;
  patch: (change: Partial<SellerDraft>) => void;
  addPhoto: (url: string) => void;
  removePhoto: (url: string) => void;
}) {
  const titleId = useId();
  const titleHint = useId();
  const bodyId = useId();
  const bodyHint = useId();
  const short = MIN_SELLER_PROSE - draft.comment.trim().length;

  return (
    <div className="relative">
      <TiltedRatingCards
        cards={WRITE_CARDS}
        className="absolute -left-4 -right-4 -top-4 -z-10 hidden h-[190px] max-sm:block"
      />

      <div className="mt-[84px] flex min-h-20 items-center gap-[17px] rounded-[12px] bg-[var(--surface-card)] px-5 py-[19px] shadow-[var(--shadow-card)]">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-[var(--accent-success)] text-white">
          <AsteriskSimple size={24} weight="bold" aria-hidden="true" />
        </span>
        <p className="text-[14px] leading-[21px] text-[var(--text-primary)]">{ratingPrompt(draft.overall)}</p>
      </div>

      <section className="-mx-4 -mb-[120px] mt-8 rounded-t-[32px] bg-[var(--surface-card)] px-7 pb-[120px] pt-9 sm:-mx-6 sm:px-8">
        <FieldHeading htmlFor={titleId} hintId={titleHint} title="Make it pop" hint="Summarize your experience in a few words" />
        <input
          id={titleId}
          aria-describedby={titleHint}
          value={draft.title}
          onChange={(e) => patch({ title: e.target.value.slice(0, MAX_SELLER_TITLE) })}
          maxLength={MAX_SELLER_TITLE}
          placeholder="Your interesting title here..."
          className={`mt-[18px] h-[53px] ${FIELD} ${draft.title ? "border-[rgba(239,88,33,0.8)]" : "border-transparent"}`}
        />
        <p className="mt-1 text-right text-[10px] font-light leading-none text-[var(--text-primary)]">
          {draft.title.length}/{MAX_SELLER_TITLE} characters
        </p>

        <FieldHeading
          htmlFor={bodyId}
          hintId={bodyHint}
          title="A penny for your thoughts"
          hint="Elaborate on why you gave the rating"
          className="mt-9"
        />
        <div className="relative mt-[18px]">
          <textarea
            id={bodyId}
            aria-describedby={bodyHint}
            value={draft.comment}
            onChange={(e) => patch({ comment: e.target.value.slice(0, MAX_SELLER_COMMENT) })}
            className={`field-sizing-content block min-h-[156px] resize-none py-4 leading-[21px] ${FIELD} border-transparent`}
          />
          {draft.comment.length === 0 ? (
            <span
              aria-hidden="true"
              className="pointer-events-none absolute left-4 top-4 text-[14px] leading-[21px] text-[rgba(32,32,32,0.3)]"
            >
              Write it <em>bluntly</em> here..
            </span>
          ) : null}
        </div>
        <p
          aria-live="polite"
          className={`mt-1 text-right text-[10px] font-light leading-none ${
            short > 0 ? "text-[var(--text-primary)]" : "text-[var(--accent-primary)]"
          }`}
        >
          {short > 0 ? `${short} characters remaining` : "I’m sure someone will appreciate this"}
        </p>

        <p className={`mt-9 ${HEADING}`}>A picture speaks a thousand words</p>
        <p className={HINT}>Share some photos of your experience</p>
        <PhotoTiles urls={draft.photoUrls} onAdd={addPhoto} onRemove={removePhoto} />
      </section>
    </div>
  );
}

/**
 * Public photos, through the same endpoint a product review's photo uses. The
 * API accepts only URLs this reviewer uploaded (photo_not_owned otherwise).
 *
 * Figma 4645:10125 / 4652:12635: 120px white tiles at radius 16 with the card
 * shadow, 12px apart, 26px under the hint. Empty: a filled 32px Image 32px from
 * the top and "Tap to upload" in 10px Regular #8c8c8c; after a photo, a 32px
 * Plus and "Add more". The remove control is not drawn; a photo needs one.
 */
function PhotoTiles({
  urls,
  onAdd,
  onRemove,
}: {
  urls: string[];
  onAdd: (url: string) => void;
  onRemove: (url: string) => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function upload(file: File) {
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
      const { url } = (await res.json()) as { url: string };
      onAdd(url);
    } catch {
      setError("Couldn't reach the server.");
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  return (
    <div className="mt-[26px]">
      <ul className="flex flex-wrap gap-3">
        {urls.map((url, i) => (
          <li
            key={url}
            className="relative h-[120px] w-[120px] overflow-hidden rounded-[16px] shadow-[var(--shadow-card)]"
          >
            <Image src={url} alt="" fill sizes="120px" className="object-cover" />
            <button
              type="button"
              onClick={() => onRemove(url)}
              aria-label={`Remove photo ${i + 1}`}
              className="absolute right-1.5 top-1.5 grid h-7 w-7 cursor-pointer place-items-center rounded-full bg-[rgba(32,32,32,0.7)] text-white"
            >
              <X size={14} weight="bold" aria-hidden="true" />
            </button>
          </li>
        ))}
        {urls.length < MAX_SELLER_PHOTOS ? (
          <li>
            <button
              type="button"
              onClick={() => input.current?.click()}
              disabled={busy}
              className={`flex h-[120px] w-[120px] cursor-pointer flex-col items-center rounded-[16px] bg-[var(--surface-card)] pt-8 text-[10px] leading-none text-[var(--base-gray-400)] shadow-[var(--shadow-card)] disabled:cursor-wait ${FOCUS_RING}`}
            >
              {urls.length === 0 ? (
                <ImageIcon size={32} weight="fill" aria-hidden="true" className="text-[var(--base-black)]" />
              ) : (
                <Plus size={32} aria-hidden="true" className="text-[var(--base-black)]" />
              )}
              <span className="mt-[9px]">{busy ? "Uploading…" : urls.length === 0 ? "Tap to upload" : "Add more"}</span>
            </button>
          </li>
        ) : null}
      </ul>
      <input
        ref={input}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        className="hidden"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void upload(file);
        }}
      />
      {error ? (
        <p role="alert" className="mt-3 text-[12px] leading-[18px] text-[var(--accent-danger)]">
          {error}
        </p>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------- done */

/**
 * Figma "Seller Review - All done" (4652:12914): "All done!", "Your review is
 * now live!" and "Make sure all the details are accurate!" in the composer's
 * heading stack; "See what your review looks like:" 35px lower and 19px in, in
 * 12px Regular trust blue, over the tilted ReviewCard; "Your latest stats:"
 * 33px under the card and 11px in; the six tilted cards from the bottom
 * corners; "View my review" pinned 32px from the bottom.
 *
 * The preview is the draft as posted: the title and the first photo, with
 * the real zero engagement a review posted seconds ago has (ReviewPreviewCard).
 */
function DoneStep({ seller, draft, user }: { seller: PickedSeller; draft: SellerDraft; user: PanelUser }) {
  return (
    <div className="relative">
      <TiltedRatingCards cards={DONE_CARDS} className="fixed inset-x-0 bottom-0 z-0 hidden h-[340px] max-sm:block" />
      <div className="relative z-10">
        <p className="text-[12px] leading-none text-[var(--text-primary)]">All done!</p>
        <h1 className="mt-2.5 text-[20px] font-medium leading-none text-[var(--accent-primary)]">
          Your review is now live!
        </h1>
        <p className="mt-[7px] text-[12px] font-light leading-[18px] text-[rgba(32,32,32,0.7)]">
          Make sure all the details are accurate!
        </p>

        <p className="ml-[19px] mt-[35px] text-[12px] leading-none text-[var(--accent-trust)]">
          See what your review looks like:
        </p>
        <ReviewPreviewCard
          username={user?.username ?? null}
          avatarUrl={user?.avatarUrl ?? null}
          productName={null}
          title={draft.title}
          photoUrl={draft.photoUrls[0] ?? null}
          className="mt-5"
        />

        <LatestStats className="mt-[33px] [&>p]:ml-[11px]" />
      </div>

      <div className="pointer-events-none fixed inset-x-0 bottom-0 z-20 pb-8">
        <div className="mx-auto w-full max-w-[42rem] px-4 sm:px-6">
          <Button href={`/sellers/${seller.id}`} fullWidth className="pointer-events-auto gap-1">
            View my review
            <ArrowRight size={20} aria-hidden="true" />
          </Button>
        </div>
      </div>
    </div>
  );
}

export default RateSellerForm;
