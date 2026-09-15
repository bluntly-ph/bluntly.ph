import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, DotOutline, Medal, QuestionMark, SealCheck } from "@phosphor-icons/react/dist/ssr";

import { AnswerForm } from "@/components/qa/AnswerForm";
import { splitQuestionBody } from "@/components/qa/ask-question-model";
import { BestAnswerButton } from "@/components/qa/BestAnswerButton";
import { answerByline, questionSubject } from "@/components/qa/question-subject-model";
import { COMPOSER_HEADING, COMPOSER_HINT } from "@/components/reviews/composer-styles";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader, type HeaderUser } from "@/components/site/SiteHeader";
import { TrustBadge } from "@/components/ui/TrustBadge";
import { getUser } from "@/lib/dal";
import { getQuestionDetail } from "@/lib/qa";
import { relativeTime } from "@/lib/relative-time";

export const metadata: Metadata = {
  title: "Question — bluntly",
};

const Dot = () => <DotOutline size={12} aria-hidden="true" className="shrink-0 text-[var(--base-gray-400)]" />;

/**
 * One question and its answers.
 *
 * NO FIGMA FRAME draws a single question; "Question Page" (4218:1856) lists a
 * product's questions. This page is built from that frame's parts: the "Questions
 * about :" heading (20px SemiBold, the first line italic) over a hairline; each
 * entry's meta in 12px ExtraLight split by a 12px DotOutline, the question in
 * 14px Bold, the "Requirements:" line in 12px Light with 10px tags on #d9d9d9 at
 * radius 4, and a 16px Medal with "Best Answer" in 12px Light; full-bleed
 * hairlines between entries. The answer box is the composers' field.
 *
 * Not drawn, because nothing serves them: "Notify me!" (no question
 * subscriptions), and the frame's product panel — price history, 3D model,
 * compare, photos, rating bars and specs — since products have no page here.
 */
export default async function QuestionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  // Parallel: the question and the viewer are independent (see app/page.tsx).
  const [question, me] = await Promise.all([getQuestionDetail(id), getUser().catch(() => null)]);
  if (!question) notFound();
  const subject = questionSubject(question);
  const { text, requirements } = splitQuestionBody(question.body);

  let user: HeaderUser = null;
  let isAsker = false;
  let canAnswer = false;
  if (me) {
    user = { username: me.username, avatarUrl: me.avatar_url };
    canAnswer = true;
    isAsker = me.id === question.asker?.id;
  }
  const answers = question.answers.length;

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={user} />
      <main className="mx-auto w-full max-w-[42rem] flex-1 px-4 pb-16 pt-5 md:px-6">
        <Link
          href="/questions"
          className="inline-flex items-center gap-1 text-[12px] font-light leading-none text-[var(--text-primary)] no-underline hover:text-[var(--accent-primary)]"
        >
          <ArrowLeft size={16} aria-hidden="true" /> All questions
        </Link>

        <h1 className="mt-5 text-[20px] font-semibold leading-[30px] text-[var(--text-primary)]">
          <span className="block italic">Questions about :</span>
          {subject.href ? (
            <Link href={subject.href} className="text-[var(--text-primary)] no-underline hover:text-[var(--accent-primary)]">
              {subject.label}
            </Link>
          ) : (
            subject.label
          )}
        </h1>

        <article className="mt-3 border-y border-[var(--line-hairline-10)] py-5">
          <p className="flex flex-wrap items-center gap-1 text-[12px] font-extralight leading-[18px] text-[var(--text-primary)]">
            {relativeTime(question.created_at)}
            <Dot />
            Asked of {question.directed_to === "seller" ? "the seller" : "other buyers"}
            {question.asker ? (
              <>
                <Dot />
                by {question.asker.display_name ?? question.asker.username}
              </>
            ) : null}
          </p>
          <h2 className="mt-2 whitespace-pre-line text-[14px] font-bold leading-[21px] text-[var(--text-primary)]">
            {text}
          </h2>
          {requirements.length > 0 ? (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className="text-[12px] font-light leading-none text-[var(--text-primary)]">Requirements:</span>
              {requirements.map((r) => (
                <span
                  key={r}
                  className="rounded-[4px] bg-[#d9d9d9] px-2 py-1 text-[10px] leading-none text-[var(--text-primary)]"
                >
                  {r}
                </span>
              ))}
            </div>
          ) : null}
          <p className="mt-3 flex flex-wrap items-center gap-1 text-[12px] font-light leading-none text-[var(--text-primary)]">
            <span className="inline-flex items-center gap-1">
              <QuestionMark size={16} aria-hidden="true" />
              {answers === 0 ? "Unanswered" : `${answers} ${answers === 1 ? "answer" : "answers"}`}
            </span>
            {question.best_answer_id ? (
              <>
                <Dot />
                <span className="inline-flex items-center gap-1">
                  <Medal size={16} aria-hidden="true" /> Best Answer
                </span>
              </>
            ) : null}
          </p>
        </article>

        <ul>
          {question.answers.map((a) => {
            const byline = answerByline(a);
            return (
              <li key={a.id} className="border-b border-[var(--line-hairline-10)] py-5">
                <div className="flex flex-wrap items-center gap-1 text-[12px] font-light leading-[18px] text-[var(--text-primary)]">
                  <span className="font-normal">{byline.name}</span>
                  {byline.seller ? (
                    <>
                      <Dot />
                      <span className="inline-flex items-center gap-1 text-[rgba(32,32,32,0.7)]">
                        <SealCheck size={16} aria-hidden="true" /> Claimed Profile
                      </span>
                    </>
                  ) : a.responder ? (
                    <>
                      <Dot />
                      <TrustBadge
                        levelName={a.responder.trust_level_name}
                        stage={a.responder.trust_stage}
                        score={a.responder.reputation_score}
                        plain
                      />
                    </>
                  ) : null}
                  <Dot />
                  <span className="font-extralight">{relativeTime(a.created_at)}</span>
                </div>
                <p className="mt-2 whitespace-pre-line text-[14px] leading-[21px] text-[var(--text-primary)]">{a.body}</p>
                {a.is_best_answer || a.is_first_responder ? (
                  <p className="mt-3 flex flex-wrap items-center gap-1 text-[12px] font-light leading-none text-[var(--text-primary)]">
                    {a.is_best_answer ? (
                      <span className="inline-flex items-center gap-1 text-[var(--accent-success)]">
                        <Medal size={16} weight="fill" aria-hidden="true" /> Best Answer
                      </span>
                    ) : null}
                    {a.is_best_answer && a.is_first_responder ? <Dot /> : null}
                    {a.is_first_responder ? "First responder" : null}
                  </p>
                ) : null}
                {isAsker && !a.is_best_answer ? (
                  <div className="mt-3">
                    <BestAnswerButton questionId={question.id} answerId={a.id} />
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>

        <section className="mt-9">
          <h2 className={COMPOSER_HEADING}>Your answer</h2>
          <p className={COMPOSER_HINT}>Share what you know from actually using it</p>
          <div className="mt-[18px]">
            <AnswerForm questionId={question.id} canAnswer={canAnswer} />
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
