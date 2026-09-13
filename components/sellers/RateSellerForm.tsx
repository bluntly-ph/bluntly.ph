"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import {
  ArrowRight,
  Asterisk,
  Check,
  Image as ImageIcon,
  LinkSimple,
  MagnifyingGlass,
  Plus,
  Star,
  X,
} from "@phosphor-icons/react/dist/ssr";

import { ComposerHeader } from "@/components/reviews/ComposerHeader";
import type { PanelUser } from "@/components/site/ProfileNavPanel";
import { Button } from "@/components/ui/Button";
import { prepareImageForUpload } from "@/lib/image";

import { ClaimStatusLine, SellerAvatar, StarRow } from "./SellerIdentity";
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
  toSellerReviewPayload,
  type SellerDraft,
  type SellerPlatform,
  type SellerReviewPayload,
} from "./seller-model";

/**
 * The seller-review composer (FR-4), built to the "Seller Review" frames:
 *
 *   Step 1 / 1-1   find the store by name
 *   Step 2 .. 2.6  stars, recommend, service, packaging, accuracy, completeness
 *   Step 3 .. 3.3  title, prose, photos
 *   All done       the posted review
 *
 * Seller reviews publish immediately — they carry no affiliate link and earn
 * nothing, so they skip the product-review moderation gate (DEVIATIONS §37);
 * a moderator can remove one afterwards. The done screen says that, rather
 * than the product composer's "held for moderation".
 */

export type PickedSeller = {
  id: string;
  display_name: string;
  platform: SellerPlatform;
  claim_status: string;
  review_count: number;
};

type Stage = "find" | "rate" | "write" | "done";

const FACE = "font-[family-name:var(--font-system)]";
const SELECTED_RING = "shadow-[var(--shadow-card),inset_0_0_0_1px_var(--accent-primary)]";

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

  function startOver() {
    setSeller(null);
    setDraft(emptySellerDraft());
    go("find");
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
          : undefined;

  return (
    <>
      <ComposerHeader
        user={user}
        onBack={back}
        backLabel={stage === "write" ? "Back to the ratings" : stage === "rate" ? "Choose another seller" : "Leave"}
      />
      <main className="relative mx-auto w-full max-w-[42rem] flex-1 px-4 pb-[140px] pt-5 sm:px-6">
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
        {stage === "done" && seller ? (
          <DoneStep seller={seller} draft={draft} user={user} onAgain={startOver} />
        ) : null}

        {error ? (
          <p
            role="alert"
            className="relative z-10 mt-6 rounded-[var(--radius-sm)] bg-[color-mix(in_srgb,var(--accent-danger)_10%,white)] px-4 py-3 text-[13px] text-[var(--accent-danger)]"
          >
            {error}
          </p>
        ) : null}
      </main>

      {stage === "rate" || stage === "write" ? (
        <div className="pointer-events-none fixed inset-x-0 bottom-0 z-20 pb-8">
          <div className="mx-auto w-full max-w-[42rem] px-4 sm:px-6">
            <Button
              type="button"
              onClick={stage === "rate" ? () => go("write") : submit}
              disabled={Boolean(blocker) || busy}
              fullWidth
              className="pointer-events-auto"
            >
              {stage === "rate" ? "Continue" : busy ? "Posting…" : "Submit"}
              {busy ? null : <ArrowRight size={18} weight="bold" aria-hidden="true" />}
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

function FindSeller({ onPick }: { onPick: (seller: PickedSeller) => void }) {
  const id = useId();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<PickedSeller[]>([]);
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
      <p className={`${FACE} text-[13px] text-[var(--text-primary)]`}>Let&rsquo;s get started!</p>
      {/* The frame reads "Who are rating today?"; the missing word is restored. */}
      <h1 className="mt-[6px] text-[length:var(--text-lg)] font-[number:var(--weight-medium)] leading-[26px] text-[var(--accent-primary)]">
        Who are you rating today?
      </h1>
      <p className={`mt-[6px] ${FACE} text-[13px] text-[var(--text-secondary)]`}>
        Find the seller. Help people buy from the right place
      </p>

      <label htmlFor={id} className="sr-only">
        Store name
      </label>
      <input
        id={id}
        value={q}
        onChange={(e) => setQ(e.target.value)}
        autoFocus
        autoComplete="off"
        placeholder="e.g Jisulife Official Store"
        className={`mt-6 h-[56px] w-full rounded-[var(--radius-pill)] border border-[var(--base-gray-600)] bg-transparent px-6 ${FACE} text-[16px] text-[var(--text-primary)] outline-none placeholder:text-[var(--text-muted)] focus-visible:border-[var(--accent-primary)]`}
      />

      {visible === null ? (
        adding ? null : (
          <div className="flex flex-col items-center py-20 text-center">
            <MagnifyingGlass size={56} aria-hidden="true" className="text-[var(--text-primary)]" />
            <p className={`mt-4 ${FACE} text-[16px] text-[var(--text-primary)]`}>
              Find the seller you bought from
            </p>
            <p className={`mt-1 ${FACE} text-[13px] text-[var(--text-secondary)]`}>
              No need for the exact store name.
              <br />
              Just type what you know.
            </p>
          </div>
        )
      ) : (
        <>
          <p className={`mt-6 ${FACE} text-[13px] text-[var(--text-primary)]`} aria-live="polite">
            {visible.length} {visible.length === 1 ? "result" : "results"} found
          </p>
          <ul className="mt-3 border-t border-[var(--line-hairline-10)]">
            {visible.map((s) => (
              <li key={s.id} className="border-b border-[var(--line-hairline-10)]">
                <button
                  type="button"
                  onClick={() => onPick(s)}
                  className="flex w-full cursor-pointer items-center gap-4 py-4 text-left hover:bg-[var(--line-hairline-10)] focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--accent-primary)]"
                >
                  <SellerAvatar name={s.display_name} size={80} />
                  <span className="min-w-0">
                    <ClaimStatusLine status={s.claim_status} />
                    <span className="mt-0.5 block truncate text-[16px] font-bold text-[var(--text-primary)]">
                      {s.display_name}
                    </span>
                    <span className={`mt-1 block ${FACE} text-[13px] text-[var(--text-secondary)]`}>
                      {s.review_count} {s.review_count === 1 ? "review" : "reviews"} ·{" "}
                      {PLATFORM_LABEL[s.platform]}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      {adding ? (
        <AddSellerForm initialName={query} onAdded={onPick} onCancel={() => setAdding(false)} />
      ) : (
        <button
          type="button"
          onClick={() => setAdding(true)}
          className={`mt-8 flex h-[48px] w-full cursor-pointer items-center gap-3 rounded-[var(--radius-sm)] bg-[var(--surface-card)] px-5 ${FACE} text-[15px] text-[var(--text-muted)] shadow-[var(--shadow-card)] hover:text-[var(--text-primary)]`}
        >
          <LinkSimple size={20} aria-hidden="true" />
          Can&rsquo;t find the seller? Add it
        </button>
      )}
    </div>
  );
}

/**
 * INTENTIONAL PRODUCT DIFFERENCE — REQUIRED FUNCTIONALITY.
 *
 * The frame offers "Can't find seller? Paste Shopee link here" and nothing
 * else. A link alone cannot name a store without fetching the marketplace
 * page, which this product does not do — and guessing a store from a URL is
 * how a rating lands on the wrong seller. So the link is kept, optional, next
 * to the store name and marketplace the API needs. The API matches by name and
 * marketplace, so adding a store that already exists returns that store.
 */
function AddSellerForm({
  initialName,
  onAdded,
  onCancel,
}: {
  initialName: string;
  onAdded: (seller: PickedSeller) => void;
  onCancel: () => void;
}) {
  const nameId = useId();
  const linkId = useId();
  const [name, setName] = useState(initialName);
  const [platform, setPlatform] = useState<SellerPlatform>("shopee");
  const [link, setLink] = useState("");
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

  const field = `h-[48px] w-full rounded-[var(--radius-sm)] bg-[var(--surface-card)] px-4 ${FACE} text-[15px] text-[var(--text-primary)] shadow-[var(--shadow-card)] outline-none placeholder:text-[var(--text-muted)] focus-visible:shadow-[var(--shadow-card),inset_0_0_0_1px_var(--accent-primary)]`;

  return (
    <form onSubmit={add} className="mt-8 flex flex-col gap-4">
      <p className={`${FACE} text-[15px] font-medium text-[var(--text-primary)]`}>Add a seller</p>
      <div>
        <label htmlFor={nameId} className={`${FACE} text-[13px] text-[var(--text-secondary)]`}>
          Store name, as the marketplace shows it
        </label>
        <input
          id={nameId}
          value={name}
          onChange={(e) => setName(e.target.value.slice(0, 160))}
          className={`mt-2 ${field}`}
        />
      </div>
      <fieldset>
        <legend className={`${FACE} text-[13px] text-[var(--text-secondary)]`}>Marketplace</legend>
        <div className="mt-2 flex flex-wrap gap-2">
          {(Object.keys(PLATFORM_LABEL) as SellerPlatform[]).map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => setPlatform(key)}
              aria-pressed={platform === key}
              className={`h-10 cursor-pointer rounded-[var(--radius-pill)] px-4 ${FACE} text-[14px] ${
                platform === key
                  ? "bg-[var(--accent-primary)] text-white"
                  : "bg-[var(--surface-card)] text-[var(--text-primary)] shadow-[var(--shadow-card)]"
              }`}
            >
              {PLATFORM_LABEL[key]}
            </button>
          ))}
        </div>
      </fieldset>
      <div>
        <label htmlFor={linkId} className={`${FACE} text-[13px] text-[var(--text-secondary)]`}>
          Store link (optional)
        </label>
        <input
          id={linkId}
          value={link}
          onChange={(e) => setLink(e.target.value)}
          inputMode="url"
          placeholder="Paste the store's Shopee or Lazada link"
          className={`mt-2 ${field}`}
        />
      </div>
      {error ? (
        <p role="alert" className="text-[13px] text-[var(--accent-danger)]">
          {error}
        </p>
      ) : null}
      <div className="flex items-center gap-4">
        <Button type="submit" disabled={!name.trim() || busy}>
          {busy ? "Adding…" : "Add seller"}
        </Button>
        <button
          type="button"
          onClick={onCancel}
          className={`cursor-pointer ${FACE} text-[14px] text-[var(--text-secondary)] underline-offset-4 hover:underline`}
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

/* ------------------------------------------------------------------- rate */

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
  return (
    <div>
      <div className="flex items-end gap-3 rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-card)]">
        <div className="min-w-0 flex-1">
          <p className={`${FACE} text-[13px] text-[var(--accent-trust)]`}>Currently reviewing</p>
          <p className={`mt-1 truncate ${FACE} text-[18px] text-[var(--text-primary)]`}>
            {seller.display_name}
          </p>
        </div>
        <button
          type="button"
          onClick={onChangeSeller}
          className={`shrink-0 cursor-pointer ${FACE} text-[16px] text-[var(--text-muted)] underline-offset-4 hover:text-[var(--text-primary)] hover:underline`}
        >
          Change
        </button>
      </div>

      <h1 className="mt-12 text-center text-[length:var(--text-lg)] font-[number:var(--weight-medium)] text-[var(--accent-primary)]">
        How was the seller?
      </h1>
      <div className="mt-5 flex justify-center gap-[6px]">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            onClick={() => patch({ overall: n })}
            aria-label={`${n} star${n > 1 ? "s" : ""}`}
            aria-pressed={draft.overall === n}
            className="cursor-pointer rounded-[6px] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-primary)]"
          >
            <Star
              size={48}
              weight="fill"
              aria-hidden="true"
              className={
                draft.overall !== null && n <= draft.overall
                  ? "text-[var(--accent-success)]"
                  : "text-[var(--base-gray-400)]"
              }
            />
          </button>
        ))}
      </div>

      <div className="mt-6 flex flex-col gap-3">
        <ChoiceCard
          tone="yes"
          value={draft.recommend}
          choice
          onPick={(recommend) => patch({ recommend })}
        >
          I recommend this seller
        </ChoiceCard>
        <ChoiceCard
          tone="no"
          value={draft.recommend}
          choice={false}
          onPick={(recommend) => patch({ recommend })}
        >
          I don&rsquo;t recommend this seller
        </ChoiceCard>
      </div>

      {/* The white sheet the frame draws under the stars, run to the bottom of
          the page — the main column's bottom padding is taken back into it. */}
      <section className="-mx-4 -mb-[140px] mt-14 rounded-t-[32px] bg-[var(--surface-card)] px-7 pb-[180px] pt-10 sm:-mx-6 sm:px-8">
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
        />
        <BinaryQuestion
          title="Ad Accuracy"
          hint="Did what arrived match the listing?"
          yes="Yes, accurate!"
          no="Not the same"
          value={draft.accuracy}
          onPick={(accuracy) => patch({ accuracy })}
        />
        <BinaryQuestion
          title="Order completeness"
          hint="Did you get exactly what you ordered?"
          yes="Exact order"
          no="Missing item"
          value={draft.completeness}
          onPick={(completeness) => patch({ completeness })}
        />
      </section>
    </div>
  );
}

/**
 * A yes/no card. As in step 2.6: the chosen card takes an orange hairline and
 * the other fades, while both keep their green tick or red cross.
 */
function ChoiceCard({
  tone,
  value,
  choice,
  onPick,
  children,
}: {
  tone: "yes" | "no";
  value: boolean | null;
  choice: boolean;
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
      className={`flex cursor-pointer items-center gap-3 rounded-[var(--radius-sm)] bg-[var(--surface-card)] px-5 py-[14px] text-left transition-opacity ${
        selected ? SELECTED_RING : "shadow-[var(--shadow-card)]"
      } ${dimmed ? "opacity-60" : ""}`}
    >
      <Icon
        size={22}
        weight="bold"
        aria-hidden="true"
        className={`shrink-0 ${tone === "yes" ? "text-[var(--accent-success)]" : "text-[var(--accent-danger)]"}`}
      />
      <span className={`${FACE} text-[15px] text-[var(--text-primary)]`}>{children}</span>
    </button>
  );
}

function QuestionHeading({ title, hint }: { title: string; hint: string }) {
  return (
    <>
      <legend className={`${FACE} text-[15px] font-medium text-[var(--text-primary)]`}>{title}</legend>
      <p className={`mt-1 ${FACE} text-[12px] text-[var(--text-secondary)]`}>{hint}</p>
    </>
  );
}

function GradeQuestion({
  title,
  hint,
  value,
  onPick,
}: {
  title: string;
  hint: string;
  value: number | null;
  onPick: (grade: number) => void;
}) {
  return (
    <fieldset className="mt-8 first:mt-0">
      <QuestionHeading title={title} hint={hint} />
      <div className="mt-3 flex flex-wrap gap-3">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            onClick={() => onPick(n)}
            aria-pressed={value === n}
            aria-label={`${n} out of 5`}
            className={`grid h-[52px] w-[52px] cursor-pointer place-items-center rounded-full ${FACE} text-[18px] ${
              value === n
                ? "bg-[var(--accent-primary)] text-white"
                : "bg-[rgb(242,242,242)] text-[var(--text-primary)] shadow-[0_4px_4px_0_var(--shadow-color-10)]"
            }`}
          >
            {n}
          </button>
        ))}
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
}: {
  title: string;
  hint: string;
  yes: string;
  no: string;
  value: boolean | null;
  onPick: (answer: boolean) => void;
}) {
  return (
    <fieldset className="mt-8">
      <QuestionHeading title={title} hint={hint} />
      <div className="mt-3 flex flex-wrap gap-3">
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
  const input = `w-full rounded-[var(--radius-sm)] bg-[var(--surface-card)] ${FACE} text-[15px] text-[var(--text-primary)] shadow-[var(--shadow-card)] outline-none placeholder:text-[var(--text-muted)] focus-visible:shadow-[var(--shadow-card),inset_0_0_0_1px_var(--accent-primary)]`;

  return (
    <div>
      <div className="mt-20 flex items-center gap-4 rounded-[var(--radius-sm)] bg-[var(--surface-card)] px-6 py-5 shadow-[var(--shadow-card)]">
        <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-[var(--accent-success)] text-white">
          <Asterisk size={24} weight="bold" aria-hidden="true" />
        </span>
        <p className={`${FACE} text-[15px] leading-[21px] text-[var(--text-primary)]`}>
          {ratingPrompt(draft.overall)}
        </p>
      </div>

      <section className="-mx-4 -mb-[140px] mt-8 rounded-t-[32px] bg-[var(--surface-card)] px-6 pb-[180px] pt-10 sm:-mx-6 sm:px-8">
        <label htmlFor={titleId} className={`block ${FACE} text-[15px] font-medium text-[var(--text-primary)]`}>
          Make it pop
        </label>
        <p id={titleHint} className={`mt-1 ${FACE} text-[12px] text-[var(--text-secondary)]`}>
          Summarize your experience in a few words
        </p>
        <input
          id={titleId}
          aria-describedby={titleHint}
          value={draft.title}
          onChange={(e) => patch({ title: e.target.value.slice(0, MAX_SELLER_TITLE) })}
          maxLength={MAX_SELLER_TITLE}
          placeholder="Your interesting title here..."
          className={`mt-3 h-[53px] px-4 ${input}`}
        />
        <p className={`mt-2 text-right ${FACE} text-[11px] text-[var(--text-secondary)]`}>
          {draft.title.length}/{MAX_SELLER_TITLE} characters
        </p>

        <label htmlFor={bodyId} className={`mt-6 block ${FACE} text-[15px] font-medium text-[var(--text-primary)]`}>
          A penny for your thoughts
        </label>
        <p id={bodyHint} className={`mt-1 ${FACE} text-[12px] text-[var(--text-secondary)]`}>
          Elaborate on why you gave the rating
        </p>
        <div className="relative mt-3">
          <textarea
            id={bodyId}
            aria-describedby={bodyHint}
            value={draft.comment}
            onChange={(e) => patch({ comment: e.target.value.slice(0, MAX_SELLER_COMMENT) })}
            className={`field-sizing-content block min-h-[150px] resize-none p-4 leading-[21px] ${input}`}
          />
          {draft.comment.length === 0 ? (
            <span
              aria-hidden="true"
              className={`pointer-events-none absolute left-4 top-4 ${FACE} text-[15px] leading-[21px] text-[var(--text-muted)]`}
            >
              Write it <em>bluntly</em> here..
            </span>
          ) : null}
        </div>
        <p
          aria-live="polite"
          className={`mt-2 text-right ${FACE} text-[11px] ${
            short > 0 ? "text-[var(--base-gray-400)]" : "text-[var(--accent-primary)]"
          }`}
        >
          {short > 0 ? `${short} characters remaining` : "I’m sure someone will appreciate this"}
        </p>

        <p className={`mt-6 ${FACE} text-[15px] font-medium text-[var(--text-primary)]`}>
          A picture speaks a thousand words
        </p>
        <p className={`mt-1 ${FACE} text-[12px] text-[var(--text-secondary)]`}>
          Share some photos of your experience
        </p>
        <PhotoTiles urls={draft.photoUrls} onAdd={addPhoto} onRemove={removePhoto} />
      </section>
    </div>
  );
}

/**
 * Public photos, through the same endpoint a product review's photo uses. The
 * API accepts only URLs this reviewer uploaded (photo_not_owned otherwise).
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
    <div className="mt-4">
      <ul className="flex flex-wrap gap-4">
        {urls.map((url, i) => (
          <li
            key={url}
            className="relative h-[120px] w-[120px] overflow-hidden rounded-[var(--radius-md)] shadow-[var(--shadow-card)]"
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
              className={`flex h-[120px] w-[120px] cursor-pointer flex-col items-center justify-center gap-2 rounded-[var(--radius-md)] bg-[var(--surface-card)] ${FACE} text-[11px] text-[var(--text-secondary)] shadow-[var(--shadow-card)] disabled:cursor-wait`}
            >
              {urls.length === 0 ? (
                <ImageIcon size={30} weight="fill" aria-hidden="true" className="text-[var(--base-black)]" />
              ) : (
                <Plus size={30} aria-hidden="true" className="text-[var(--base-black)]" />
              )}
              {busy ? "Uploading…" : urls.length === 0 ? "Tap to upload" : "Add more"}
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
        <p role="alert" className="mt-3 text-[13px] text-[var(--accent-danger)]">
          {error}
        </p>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------- done */

/**
 * "Seller Review - All done.png", with two things left out on purpose.
 *
 * "Your latest stats" (reviews posted, people helped, commission earned) and
 * the preview card's vote and comment counts: a review posted seconds ago has
 * no votes or comments, and seller reviews earn nothing, so every one of those
 * figures would be invented. The preview keeps what is real — the reviewer,
 * the stars, the title and the first photo.
 */
function DoneStep({
  seller,
  draft,
  user,
  onAgain,
}: {
  seller: PickedSeller;
  draft: SellerDraft;
  user: PanelUser;
  onAgain: () => void;
}) {
  return (
    <div className="pt-6">
      <p className={`${FACE} text-[13px] text-[var(--text-primary)]`}>All done!</p>
      <h1 className="mt-[6px] text-[24px] font-semibold leading-[28px] text-[var(--accent-primary)]">
        Your seller review is posted!
      </h1>
      <p className={`mt-[10px] ${FACE} text-[13px] leading-[18px] text-[var(--text-secondary)]`}>
        It&rsquo;s on {seller.display_name}&rsquo;s page now. Moderators can still remove a review
        that breaks the community guidelines.
      </p>

      <p className={`mt-8 ${FACE} text-[13px] text-[var(--accent-trust)]`}>
        See what your review looks like:
      </p>
      <div className="mt-4 flex gap-4 rounded-[var(--radius-md)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-card)]">
        <div className="min-w-0 flex-1">
          <p className={`${FACE} text-[13px] text-[var(--text-secondary)]`}>
            {user?.username ?? "You"}
          </p>
          <StarRow value={draft.overall} size={16} className="mt-2" />
          <p className="mt-2 text-[16px] font-bold text-[var(--text-primary)]">{draft.title.trim()}</p>
        </div>
        {draft.photoUrls[0] ? (
          <span className="relative h-[100px] w-[100px] shrink-0 overflow-hidden rounded-[var(--radius-md)]">
            <Image src={draft.photoUrls[0]} alt="" fill sizes="100px" className="object-cover" />
          </span>
        ) : null}
      </div>

      <div className="mt-10 flex flex-col items-center gap-3">
        <Button href={`/sellers/${seller.id}`} fullWidth>
          View my review
          <ArrowRight size={18} weight="bold" aria-hidden="true" />
        </Button>
        <button
          type="button"
          onClick={onAgain}
          className={`cursor-pointer ${FACE} text-[14px] text-[var(--text-primary)] underline-offset-4 hover:underline`}
        >
          Rate another seller
        </button>
      </div>
    </div>
  );
}

export default RateSellerForm;
