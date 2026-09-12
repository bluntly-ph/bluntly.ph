import Link from "next/link";
import { Medal, Question as QuestionMark } from "@phosphor-icons/react/dist/ssr";

import type { Question } from "@/lib/qa";

/**
 * A question as it appears in the Questions tab of /search.
 *
 * Matched to the owner-provided reference for that tab: a muted activity line,
 * the product name as the headline, the question itself quoted in italics, and
 * an answer summary underneath.
 *
 * TWO THINGS IN THE REFERENCE ARE DELIBERATELY NOT RENDERED, because no data
 * behind them exists and inventing it would make the card lie:
 *
 *  - "Topics:" chips (Noise, Battery, Portability). Questions carry no topics
 *    or tags in this product; there is no field to populate them from.
 *  - The product thumbnail on the right. `QuestionOut` carries `product_name`
 *    but no image, so there is nothing to show without a second per-row fetch
 *    for a decorative element.
 *
 * Both become straightforward once the data exists. The reference's counts are
 * example content and are never hardcoded: every number here is live.
 */

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days}d ago`;
  const weeks = Math.round(days / 7);
  if (weeks < 52) return `${weeks}w ago`;
  return `${Math.round(weeks / 52)}y ago`;
}

export function QuestionResultRow({ question }: { question: Question }) {
  const unanswered = question.answer_count === 0;
  const answers = question.answer_count;

  return (
    <li className="border-b border-[var(--line-hairline-10)]">
      <Link
        href={`/questions/${question.id}`}
        className="flex flex-col gap-1.5 py-4 no-underline focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--accent-primary)]"
      >
        <p className="text-[12px] text-[var(--text-secondary)]">
          {answers} {answers === 1 ? "answer" : "answers"}
          {" · "}
          {relativeTime(question.created_at)}
        </p>

        <h2 className="text-[15px] font-bold text-[var(--text-primary)]">
          {question.product_name ?? "Unnamed product"}
        </h2>

        <p className="text-[14px] italic text-[var(--text-primary)]">
          “{question.body}”
        </p>

        <p className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-[var(--text-secondary)]">
          <span className="inline-flex items-center gap-1">
            <QuestionMark size={14} aria-hidden="true" />
            {unanswered ? "Unanswered" : `${answers} answered`}
          </span>
          {question.best_answer_id ? (
            <span className="inline-flex items-center gap-1 text-[var(--accent-trust)]">
              <Medal size={14} aria-hidden="true" /> Best answer
            </span>
          ) : null}
        </p>
      </Link>
    </li>
  );
}

export default QuestionResultRow;
