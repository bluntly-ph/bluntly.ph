import Link from "next/link";
import { DotOutline, Medal, QuestionMark } from "@phosphor-icons/react/dist/ssr";

import { questionSubject } from "@/components/qa/question-subject-model";
import type { Question } from "@/lib/qa";

/**
 * A question in the Questions tab of /search: Figma "QuestionPreviewCard"
 * (7158:4877), as placed in "Mobile Search Page for Reviewers" (3481:1894,
 * which is the Questions tab whatever its name says). Read 2026-09-14.
 *
 * Phone values from the component, 8px apart: the meta line in 12px Poppins
 * ExtraLight, the product in 14px Bold, the question quoted in 14px Italic
 * within 226px, and the answer summary — 16px QuestionMark and Medal glyphs
 * with 12px Light labels, split by a 12px DotOutline.
 *
 * INTENTIONAL PRODUCT DIFFERENCES, because no data behind them exists and
 * inventing it would make the card lie:
 *
 *  - "3 active" in the meta line. Nothing counts active participants, so the
 *    line carries the age alone.
 *  - "Topics:" chips (Noise, Battery, Portability). Questions carry no topics.
 *  - The 100px product thumbnail. `QuestionOut` carries `product_name` but no
 *    image.
 */

const Dot = () => (
  <DotOutline size={12} aria-hidden="true" className="shrink-0 text-[var(--base-gray-400)]" />
);

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
  const answers = question.answer_count;

  return (
    <li className="border-b border-[var(--line-hairline-10)]">
      <Link
        href={`/questions/${question.id}`}
        className="flex flex-col gap-2 px-4 pb-6 pt-5 text-[var(--text-primary)] no-underline focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-[var(--accent-primary)] md:px-0 md:py-4"
      >
        <p className="text-[12px] font-extralight leading-[18px]">
          {relativeTime(question.created_at)}
        </p>

        <h2 className="text-[14px] font-bold leading-[21px]">{questionSubject(question).label}</h2>

        <p className="line-clamp-2 text-[14px] italic leading-[21px] max-md:max-w-[226px]">
          “{question.body}”
        </p>

        <p className="flex flex-wrap items-center gap-1 text-[12px] font-light leading-none">
          <span className="inline-flex items-center gap-1">
            <QuestionMark size={16} aria-hidden="true" />
            {answers === 0 ? "Unanswered" : `${answers} ${answers === 1 ? "answer" : "answers"}`}
          </span>
          {question.best_answer_id ? (
            <>
              <Dot />
              <span className="inline-flex items-center gap-1">
                <Medal size={16} aria-hidden="true" /> Best answer
              </span>
            </>
          ) : null}
        </p>
      </Link>
    </li>
  );
}

export default QuestionResultRow;
