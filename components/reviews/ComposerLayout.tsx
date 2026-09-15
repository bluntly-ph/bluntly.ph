"use client";

import { Check } from "@phosphor-icons/react";
import type { ReactNode } from "react";

/**
 * The composers' page frame — Write a review, Rate a seller, Ask a question.
 *
 * PHONE (below `md`): exactly the Figma frames. One column, 16px sides (24 from
 * `sm`), 120px of bottom padding so nothing is trapped under the pill that
 * ComposerActions pins to the viewport.
 *
 * WEBSITE (`md` and up): the file has no desktop frame for these flows, and the
 * phone column stretched across a monitor with a pinned pill over the fields is
 * what the owner rejected (review, 2026-09-16: "not just a compressed mobile on
 * a big screen"). So from `md` the page is two columns — a sticky panel naming
 * what is being reviewed and where the writer is in the flow, and the step
 * itself at a readable measure — with the action inline under the step.
 *
 *   md   13rem panel, 2rem gap, the step takes the rest (464px at 768)
 *   lg   16rem panel, 4rem gap, the step capped at 42rem; 66rem overall, which
 *        is exactly those three plus the 2rem sides, so the header's arrow and
 *        avatar line up with the panel and the step's right edge
 */
export function ComposerLayout({ aside, children }: { aside: ReactNode; children: ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-[42rem] flex-1 px-4 pb-[120px] pt-4 sm:px-6 md:grid md:max-w-[66rem] md:grid-cols-[13rem_minmax(0,1fr)] md:items-start md:gap-8 md:px-8 md:pb-20 md:pt-10 lg:grid-cols-[16rem_minmax(0,42rem)] lg:gap-16">
      <aside className="hidden md:sticky md:top-[104px] md:block">{aside}</aside>
      <main className="min-w-0">{children}</main>
    </div>
  );
}

export type ComposerStep = {
  label: string;
  /**
   * The number the step's own screen shows ("Step 3 out of 7"). Left out for a
   * screen the flow does not count, such as picking the product before the
   * review's seven steps, which gets a dot instead.
   */
  number?: number;
  state: "done" | "current" | "todo";
  /** Offered on finished steps only: going back is safe, skipping ahead is not. */
  onSelect?: () => void;
};

/**
 * The website panel: the flow's name, the thing being written about, the steps
 * with the finished ones reachable again, and one line of what happens next.
 * In the composers' own language — a white card at radius 16 with the card
 * shadow, brand orange for where you are, the success green for what is done.
 */
export function ComposerSteps({
  flow,
  subjectLabel,
  subject,
  steps,
  note,
}: {
  flow: string;
  subjectLabel: string;
  /** Null until it has been picked. */
  subject: string | null;
  steps: ComposerStep[];
  note?: ReactNode;
}) {
  return (
    <div className="rounded-[16px] bg-[var(--surface-card)] p-6 text-[var(--text-primary)] shadow-[var(--shadow-card)]">
      <p className="text-[20px] font-medium leading-none text-[var(--accent-primary)]">{flow}</p>

      <div className="mt-5 rounded-[12px] bg-[var(--surface-app)] px-4 py-3">
        <p className="text-[10px] font-light leading-none text-[rgba(32,32,32,0.7)]">{subjectLabel}</p>
        <p
          className={`mt-1.5 line-clamp-2 text-[14px] leading-[1.35] [overflow-wrap:anywhere] ${
            subject ? "font-medium" : "font-light text-[rgba(32,32,32,0.5)]"
          }`}
        >
          {subject ?? "Not picked yet"}
        </p>
      </div>

      <ol className="mt-5 flex flex-col gap-1">
        {steps.map((step) => {
          const marker = (
            <span
              aria-hidden="true"
              className={`grid h-6 w-6 shrink-0 place-items-center rounded-full text-[11px] leading-none ${
                step.state === "done"
                  ? "bg-[var(--accent-success)] text-white"
                  : step.state === "current"
                    ? "bg-[var(--accent-primary)] text-white"
                    : "text-[var(--base-gray-400)] shadow-[inset_0_0_0_1px_var(--line-hairline-30)]"
              }`}
            >
              {step.state === "done" ? (
                <Check size={12} weight="bold" />
              ) : step.number !== undefined ? (
                step.number
              ) : (
                <span className="h-1.5 w-1.5 rounded-full bg-current" />
              )}
            </span>
          );
          const text = (
            <span
              className={`min-w-0 text-[13px] leading-[1.3] ${
                step.state === "current"
                  ? "font-medium text-[var(--accent-primary)]"
                  : step.state === "done"
                    ? "text-[var(--text-primary)]"
                    : "font-light text-[rgba(32,32,32,0.5)]"
              }`}
            >
              {step.label}
            </span>
          );
          return (
            <li key={step.label} aria-current={step.state === "current" ? "step" : undefined}>
              {step.onSelect ? (
                <button
                  type="button"
                  onClick={step.onSelect}
                  className="-mx-2 flex w-[calc(100%+1rem)] cursor-pointer items-center gap-3 rounded-[10px] px-2 py-1.5 text-left hover:bg-[var(--line-hairline-10)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]"
                >
                  {marker}
                  {text}
                  <span className="sr-only"> (done, go back to this step)</span>
                </button>
              ) : (
                <span className="flex items-center gap-3 py-1.5">
                  {marker}
                  {text}
                  {step.state === "done" ? <span className="sr-only"> (done)</span> : null}
                </span>
              )}
            </li>
          );
        })}
      </ol>

      {note ? (
        <p className="mt-5 border-t border-[var(--line-hairline-10)] pt-4 text-[12px] font-light leading-[18px] text-[rgba(32,32,32,0.7)]">
          {note}
        </p>
      ) : null}
    </div>
  );
}

/**
 * Where a step's action lives.
 *
 * Phone: pinned to the viewport 32px from the bottom, as every step frame draws
 * it, over a click-through strip so the page under its margins stays usable.
 *
 * Website: inline under the step, after a hairline — the reason the action is
 * still disabled written beside it (the phone keeps that in the live region
 * only, because the frames draw no text there), and the pill at its natural
 * width on the right.
 */
export function ComposerActions({
  hint,
  error,
  children,
}: {
  /** Why the action is not available yet. Shown from `md`; announced elsewhere. */
  hint?: string | null;
  error?: string | null;
  children: ReactNode;
}) {
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-0 z-20 pb-8 md:pointer-events-auto md:static md:z-auto md:mt-10 md:pb-0">
      <div className="mx-auto w-full max-w-[42rem] px-4 sm:px-6 md:max-w-none md:px-0">
        {error ? (
          <p
            role="alert"
            className="pointer-events-auto mb-2 rounded-[12px] bg-[var(--surface-card)] px-4 py-3 text-[12px] leading-[18px] text-[var(--accent-danger)] shadow-[var(--shadow-card)] md:mb-4"
          >
            {error}
          </p>
        ) : null}
        <div className="md:flex md:items-center md:justify-end md:gap-6 md:border-t md:border-[var(--line-hairline-10)] md:pt-6">
          {hint ? (
            <p
              aria-hidden="true"
              className="hidden text-[12px] font-light leading-[18px] text-[rgba(32,32,32,0.7)] md:mr-auto md:block"
            >
              {hint}
            </p>
          ) : null}
          {children}
        </div>
      </div>
    </div>
  );
}

/** The pill inside ComposerActions: full width on the phone, natural on the website. */
export const COMPOSER_ACTION_BUTTON = "pointer-events-auto gap-1 md:w-auto md:min-w-[14rem] md:shrink-0";

export default ComposerLayout;
