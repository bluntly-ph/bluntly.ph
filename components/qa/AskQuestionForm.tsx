"use client";

import { useRouter } from "next/navigation";
import { useEffect, useId, useRef, useState } from "react";
import { ArrowRight, Coin, Coins, PiggyBank, Plus, Storefront, Users } from "@phosphor-icons/react/dist/ssr";

import { COMPOSER_FOCUS_RING, COMPOSER_HEADING, COMPOSER_HINT } from "@/components/reviews/composer-styles";
import { ComposerGrid, ComposerHeader } from "@/components/reviews/ComposerHeader";
import { CurrentlyReviewingCard } from "@/components/reviews/CurrentlyReviewingCard";
import { LatestStats } from "@/components/reviews/LatestStats";
import { MascotPrompt } from "@/components/reviews/MascotPrompt";
import { ProductPicker, type PickedProduct } from "@/components/reviews/ProductPicker";
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
import { usablePhoto } from "@/lib/image";

import {
  MAX_QUESTION_TEXT,
  MIN_QUESTION_CHARS,
  QUESTION_REQUIREMENTS,
  composeQuestionBody,
  type QuestionRequirement,
} from "./ask-question-model";

/**
 * Ask a question (FR-5), built to the "Question Page" frames, read from Figma
 * 2026-09-15:
 *
 *   who       Question Page - Buyer or Seller (4682:14203), over step 1
 *   product   Step 1 (4705:14719, idle) and with results (4709:14832)
 *   question  Step 2 (4695:14599) and Step 2.3 (4742:15580, filled)
 *   done      Step 3 (4742:15979)
 *
 * The progress line is the frames' own: grey on step 1, 312 of 390px orange on
 * step 2, all green on step 3.
 *
 * INTENTIONAL PRODUCT DIFFERENCES:
 *  - "Would you like to share a photo?" is not drawn: a question has no photo
 *    in the API, so an upload here would be accepted and then dropped.
 *  - The specifics ("Experience", "Pros & Cons", …) have no field of their own
 *    either. They travel as a last "Looking for:" line of the question, which
 *    answerers read as written and the question pages show as the frame's
 *    "Requirements:" tags (ask-question-model). Future work: a column.
 *  - Step 2's pill posts the question, so it says "Submit" as the other
 *    composers' last steps do; the frame's "Continue" promises another step.
 *  - Asking a seller changes the hint and the step 3 blurb from "other buyers"
 *    to "the seller".
 *  - The stats are the member's real dashboard figures (see LatestStats).
 */

type Stage = "product" | "question" | "done";
type Audience = "buyers" | "seller";

const PROGRESS: Record<Stage, number> = { product: 0, question: 312 / 390, done: 1 };

/** Step 1's cards, "Question Page - Step 1" (4705:14719), measured below the bar. */
const PRODUCT_CARDS: TiltedCard[] = [
  { x: -123, top: 325, tilt: 5, faded: true, stars: starRow(5, STAR_GREEN) },
  { x: -106, top: 271, tilt: 5, faded: true, stars: starRow(4, STAR_GREEN) },
  { x: -90, top: 216, tilt: 5, faded: true, stars: starRow(2, fadedStar(STAR_CORAL)) },
  { x: 363, bottom: -8, tilt: -5, faded: true, anchorRight: true, starsStart: true, stars: starRow(5, STAR_GREEN) },
  { x: 347, bottom: 46, tilt: -5, faded: true, anchorRight: true, starsStart: true, stars: starRow(4, STAR_GREEN) },
  { x: 330, bottom: 101, tilt: -5, faded: true, anchorRight: true, starsStart: true, stars: starRow(3, fadedStar(STAR_YELLOW)) },
];

/** Step 2's cards behind the product card (4695:14599), from the bar down. */
const QUESTION_CARDS: TiltedCard[] = [
  { x: -134, top: 73, tilt: 5, faded: true, stars: starRow(5, STAR_GREEN) },
  { x: -117, top: 19, tilt: 5, faded: true, stars: starRow(4, STAR_GREEN) },
  { x: -100, top: -36, tilt: 5, faded: true, stars: starRow(2, fadedStar(STAR_CORAL)) },
  { x: 358, top: 154, tilt: -5, faded: true, anchorRight: true, starsStart: true, stars: starRow(5, STAR_GREEN) },
  { x: 342, top: 100, tilt: -5, faded: true, anchorRight: true, starsStart: true, stars: starRow(4, STAR_GREEN) },
  { x: 325, top: 45, tilt: -5, faded: true, anchorRight: true, starsStart: true, stars: starRow(3, fadedStar(STAR_YELLOW)) },
];

export function AskQuestionForm({ user }: { user: PanelUser }) {
  const router = useRouter();
  const [stage, setStage] = useState<Stage>("product");
  const [audience, setAudience] = useState<Audience | null>(null);
  const [product, setProduct] = useState<PickedProduct | null>(null);
  const [text, setText] = useState("");
  const [requirements, setRequirements] = useState<QuestionRequirement[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [postedId, setPostedId] = useState<string | null>(null);

  function go(next: Stage) {
    setError(null);
    setStage(next);
    window.scrollTo({ top: 0 });
  }

  function toggle(r: QuestionRequirement) {
    setRequirements((list) => (list.includes(r) ? list.filter((x) => x !== r) : [...list, r]));
  }

  const short = MIN_QUESTION_CHARS - text.trim().length;
  const blocker = stage === "question" && short > 0 ? `Write at least ${MIN_QUESTION_CHARS} characters.` : null;

  async function submit() {
    if (!product || blocker || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/bff/api/v1/questions", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          product_id: product.id,
          body: composeQuestionBody(text, requirements),
          directed_to: audience ?? "buyers",
        }),
      });
      if (!res.ok) {
        const p = (await res.json().catch(() => ({}))) as { detail?: string };
        setError(p.detail ?? "Couldn't post your question.");
        return;
      }
      const created = (await res.json()) as { id: string };
      setPostedId(created.id);
      go("done");
    } catch {
      setError("Couldn't reach the server. Try again.");
    } finally {
      setBusy(false);
    }
  }

  const back =
    stage === "product"
      ? () => router.back()
      : stage === "question"
        ? () => go("product")
        : () => router.push(postedId ? `/questions/${postedId}` : "/questions");

  return (
    <>
      <ComposerHeader
        user={user}
        onBack={back}
        backLabel={stage === "question" ? "Choose another product" : stage === "done" ? "Go to your question" : "Leave"}
        progress={PROGRESS[stage]}
      />
      <ComposerGrid />
      <main className="mx-auto w-full max-w-[42rem] flex-1 px-4 pb-[120px] pt-4 sm:px-6">
        {stage === "product" ? (
          <ProductPicker
            title="Mirror, mirror on the wall"
            blurb="Find the product. Ask a question. Let people answer."
            placeholder="e.g Anker Zolo Powerbank"
            searchLabel="Search for the product your question is about"
            fieldClassName="mt-[19px]"
            decorCards={PRODUCT_CARDS}
            emptyHint={false}
            onPick={(p) => {
              setProduct(p);
              go("question");
            }}
          />
        ) : null}
        {stage === "question" && product ? (
          <QuestionStep
            product={product}
            audience={audience ?? "buyers"}
            text={text}
            setText={setText}
            requirements={requirements}
            toggle={toggle}
            onChangeProduct={() => go("product")}
          />
        ) : null}
        {stage === "done" && product && postedId ? (
          <DoneStep user={user} product={product} audience={audience ?? "buyers"} text={text} questionId={postedId} />
        ) : null}
      </main>

      {stage === "product" && audience === null ? <AudienceDialog onChoose={setAudience} /> : null}

      {stage === "question" ? (
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
              onClick={submit}
              disabled={Boolean(blocker) || busy}
              fullWidth
              className="pointer-events-auto gap-1"
            >
              {busy ? "Posting…" : "Submit"}
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

/* -------------------------------------------------------------------- who */

/**
 * "Question Page - Buyer or Seller" (4682:14203): a 358x407 card in the page
 * colour at radius 12 with the card shadow. "How can we help you?" 24px in, in
 * 20px Medium brand orange; Bunbun under the bubble "Who do you want to answer
 * your question?" (the composer's MascotPrompt, whose insets are this card's);
 * coins and a piggy bank in the success green at 30%; and 263px down two 52px
 * white options at radius 12 under a 0 4px 2px shadow at 10%, 8px apart — a
 * 20px Users or Storefront in #8c8c8c 8px before 14px Regular.
 *
 * Closing it without choosing asks other buyers, the API's own default.
 */
function AudienceDialog({ onChoose }: { onChoose: (audience: Audience) => void }) {
  const titleId = useId();
  const panel = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Focus the dialog itself, not its first option: a programmatic focus on
    // the option draws its focus ring before the reader has chosen anything.
    panel.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onChoose("buyers");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onChoose]);

  const option = `flex h-[52px] w-full cursor-pointer items-center gap-2 rounded-[12px] bg-[var(--surface-card)] px-4 text-left text-[14px] leading-none text-[var(--text-primary)] drop-shadow-[0_4px_2px_rgba(0,0,0,0.1)] hover:text-[var(--accent-primary)] ${COMPOSER_FOCUS_RING}`;
  const coin = "absolute text-[color-mix(in_srgb,var(--accent-success)_30%,transparent)]";

  return (
    <div
      className="fixed inset-0 z-40 grid place-items-center bg-[rgba(0,0,0,0.25)] px-4"
      onClick={() => onChoose("buyers")}
    >
      <div
        ref={panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        // The container takes focus only so a keyboard lands inside the dialog;
        // it is not a control, so it must not draw the global focus ring (which
        // an utility class cannot override). Its two options keep theirs.
        style={{ outline: "none" }}
        onClick={(e) => e.stopPropagation()}
        className="relative h-[407px] w-full max-w-[358px] overflow-hidden rounded-[12px] bg-[var(--surface-app)] shadow-[var(--shadow-card)] outline-none"
      >
        <h2
          id={titleId}
          className="absolute left-6 top-6 text-[20px] font-medium leading-none text-[var(--accent-primary)]"
        >
          How can we help you?
        </h2>
        <span aria-hidden="true" className="pointer-events-none">
          <PiggyBank size={32} weight="light" className={`${coin} left-6 top-[107px]`} />
          <Coin size={24} weight="light" className={`${coin} left-[45px] top-[132px]`} />
          <Coins size={24} weight="light" className={`${coin} left-[57px] top-[120px]`} />
          <Coins size={24} weight="light" className={`${coin} left-[123px] top-[216px]`} />
          <Coin size={24} weight="light" className={`${coin} left-[310px] top-[186px] -scale-x-100`} />
          <Coins size={24} weight="light" className={`${coin} left-[298px] top-[174px] -scale-x-100`} />
          <Coin size={24} weight="light" className={`${coin} left-[274px] top-[197px] -scale-x-100`} />
        </span>
        <MascotPrompt className="absolute inset-x-0 top-[82px]">Who do you want to answer your question?</MascotPrompt>
        <div className="absolute inset-x-6 top-[263px] flex flex-col gap-2">
          <button type="button" onClick={() => onChoose("buyers")} className={option}>
            <Users size={20} aria-hidden="true" className="shrink-0 text-[var(--base-gray-400)]" />
            I want to ask other buyers
          </button>
          <button type="button" onClick={() => onChoose("seller")} className={option}>
            <Storefront size={20} aria-hidden="true" className="shrink-0 text-[var(--base-gray-400)]" />
            I want to ask a seller
          </button>
        </div>
      </div>
    </div>
  );
}

/* --------------------------------------------------------------- question */

/**
 * "Question Page - Step 2" (4695:14599) / 2.3 (4742:15580): the product card;
 * 56px lower the white sheet at radius 32, 36px in from its top and 28px from
 * its sides. "What's your main question?" over a 156px white field at radius 16
 * with the card shadow, the counter 4px under it in 10px Light — "Good
 * question!" in brand orange once it is long enough, when the field takes an
 * orange line. 36px lower the specifics: 52px chips at radius 12, white at 30%
 * with a 0 4px 4px shadow at 10%, 12px apart, a 20px Plus 8px before 14px
 * Regular; a chosen chip takes the orange line and a green plus.
 */
function QuestionStep({
  product,
  audience,
  text,
  setText,
  requirements,
  toggle,
  onChangeProduct,
}: {
  product: PickedProduct;
  audience: Audience;
  text: string;
  setText: (text: string) => void;
  requirements: QuestionRequirement[];
  toggle: (r: QuestionRequirement) => void;
  onChangeProduct: () => void;
}) {
  const bodyId = useId();
  const bodyHint = useId();
  const specificsHint = useId();
  const short = MIN_QUESTION_CHARS - text.trim().length;

  return (
    <div className="relative">
      <TiltedRatingCards
        cards={QUESTION_CARDS}
        className="absolute -left-4 -right-4 -top-4 -z-10 hidden h-[260px] max-sm:block"
      />

      <CurrentlyReviewingCard
        label="Product in question:"
        labelInset={false}
        name={product.canonical_name ?? "Unnamed product"}
        onChange={onChangeProduct}
      />

      <section className="-mx-4 -mb-[120px] mt-14 rounded-t-[32px] bg-[var(--surface-card)] px-7 pb-[120px] pt-9 sm:-mx-6 sm:px-8">
        <label htmlFor={bodyId} className={`block ${COMPOSER_HEADING}`}>
          What&rsquo;s your main question?
        </label>
        <p id={bodyHint} className={COMPOSER_HINT}>
          Ask your main question
        </p>
        <div className="relative mt-[18px]">
          <textarea
            id={bodyId}
            aria-describedby={bodyHint}
            value={text}
            onChange={(e) => setText(e.target.value.slice(0, MAX_QUESTION_TEXT))}
            className={`field-sizing-content block min-h-[156px] w-full resize-none rounded-[16px] border bg-[var(--surface-card)] px-[15px] py-4 text-[14px] leading-[21px] text-[var(--text-primary)] shadow-[var(--shadow-card)] outline-none focus-visible:border-[var(--accent-primary)] ${
              short > 0 ? "border-transparent" : "border-[rgba(239,88,33,0.8)]"
            }`}
          />
          {text.length === 0 ? (
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
          {short > 0 ? `${short} characters remaining` : "Good question!"}
        </p>

        <fieldset aria-describedby={specificsHint} className="mt-9 min-w-0">
          <legend className={COMPOSER_HEADING}>Are there any specifics you&rsquo;d like to know?</legend>
          <p id={specificsHint} className={COMPOSER_HINT}>
            {audience === "seller" ? "Help the seller answer your question" : "Help other buyers answer your question"}
          </p>
          <div className="mt-[18px] flex flex-wrap gap-3">
            {QUESTION_REQUIREMENTS.map((r) => {
              const on = requirements.includes(r);
              return (
                <button
                  key={r}
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggle(r)}
                  className={`flex h-[52px] cursor-pointer items-center gap-2 rounded-[12px] border bg-[rgba(255,255,255,0.3)] px-[15px] text-[14px] leading-none text-[var(--text-primary)] shadow-[0_4px_4px_0_var(--shadow-color-10)] ${COMPOSER_FOCUS_RING} ${
                    on ? "border-[rgba(239,88,33,0.8)]" : "border-transparent"
                  }`}
                >
                  <Plus
                    size={20}
                    weight="light"
                    aria-hidden="true"
                    className={`shrink-0 ${on ? "text-[var(--accent-success)]" : "text-[var(--base-gray-400)]"}`}
                  />
                  {r}
                </button>
              );
            })}
          </div>
        </fieldset>
      </section>
    </div>
  );
}

/* ------------------------------------------------------------------- done */

/**
 * "Question Page - Step 3" (4742:15979): "All done!", "Now, we wait.." and the
 * patience line in the composer heading stack; "View your question here:" 35px
 * lower and 14px in, over the tilted card; "Your latest stats:" 32px under the
 * card and 11px in; the six tilted cards from the bottom corners; "View my
 * question" pinned 32px from the bottom.
 */
function DoneStep({
  user,
  product,
  audience,
  text,
  questionId,
}: {
  user: PanelUser;
  product: PickedProduct;
  audience: Audience;
  text: string;
  questionId: string;
}) {
  return (
    <div className="relative">
      <TiltedRatingCards cards={DONE_CARDS} className="fixed inset-x-0 bottom-0 z-0 hidden h-[340px] max-sm:block" />
      <div className="relative z-10">
        <p className="text-[12px] leading-none text-[var(--text-primary)]">All done!</p>
        <h1 className="mt-2.5 text-[20px] font-medium leading-none text-[var(--accent-primary)]">Now, we wait..</h1>
        <p className="mt-[7px] text-[12px] font-light leading-[18px] text-[rgba(32,32,32,0.7)]">
          A little patience goes a long way. Give {audience === "seller" ? "the seller" : "other buyers"} time to
          answer your question!
        </p>

        <p className="ml-[14px] mt-[35px] text-[12px] leading-none text-[var(--accent-trust)]">
          View your question here:
        </p>
        <ReviewPreviewCard
          username={user?.username ?? null}
          avatarUrl={user?.avatarUrl ?? null}
          productName={null}
          title={text}
          photoUrl={usablePhoto(product.image_url) ?? null}
          className="mt-[21px]"
        />

        <LatestStats className="mt-8 [&>p]:ml-[11px]" />
      </div>

      <div className="pointer-events-none fixed inset-x-0 bottom-0 z-20 pb-8">
        <div className="mx-auto w-full max-w-[42rem] px-4 sm:px-6">
          <Button href={`/questions/${questionId}`} fullWidth className="pointer-events-auto gap-1">
            View my question
            <ArrowRight size={20} aria-hidden="true" />
          </Button>
        </div>
      </div>
    </div>
  );
}

export default AskQuestionForm;
