import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { CaretLeft, Medal, SealCheck } from "@phosphor-icons/react/dist/ssr";
import Link from "next/link";

import { AnswerForm } from "@/components/qa/AnswerForm";
import { BestAnswerButton } from "@/components/qa/BestAnswerButton";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader, type HeaderUser } from "@/components/site/SiteHeader";
import { TrustBadge } from "@/components/ui/TrustBadge";
import { getUser } from "@/lib/dal";
import { getQuestionDetail } from "@/lib/qa";

export const metadata: Metadata = {
  title: "Question — bluntly",
};

export default async function QuestionPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  // Parallel: the question and the viewer are independent (see app/page.tsx).
  const [question, me] = await Promise.all([
    getQuestionDetail(id),
    getUser().catch(() => null),
  ]);
  if (!question) notFound();

  let user: HeaderUser = null;
  let isAsker = false;
  let canAnswer = false;
  if (me) {
    user = { username: me.username, avatarUrl: me.avatar_url };
    canAnswer = true;
    isAsker = me.id === question.asker?.id;
  }

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={user} />
      <main className="mx-auto w-full max-w-[44rem] flex-1 px-6 py-8 lg:py-10">
        <Link
          href="/questions"
          className="inline-flex items-center gap-1 text-[13px] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
        >
          <CaretLeft size={16} /> All questions
        </Link>

        <div className="mt-4 flex flex-wrap items-center gap-2 text-[12px] text-[var(--text-muted)]">
          {question.product_name ? (
            <span className="rounded-[var(--radius-md)] bg-[var(--surface-card)] px-2.5 py-1 text-[var(--text-secondary)] shadow-[var(--shadow-hairline-inset)]">
              {question.product_name}
            </span>
          ) : null}
          <span>
            Directed to {question.directed_to === "seller" ? "the seller" : "other buyers"}
          </span>
        </div>

        <h1 className="mt-3 text-[22px] font-bold leading-snug text-[var(--text-primary)]">
          {question.body}
        </h1>
        {question.asker ? (
          <p className="mt-1 text-[13px] text-[var(--text-secondary)]">
            asked by {question.asker.display_name ?? question.asker.username}
          </p>
        ) : null}

        <h2 className="mt-8 text-[16px] font-semibold text-[var(--text-primary)]">
          {question.answers.length} answer{question.answers.length === 1 ? "" : "s"}
        </h2>

        <ul className="mt-4 flex flex-col gap-3">
          {question.answers.map((a) => (
            <li
              key={a.id}
              className={`rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-4 shadow-[var(--shadow-hairline-inset)] ${
                a.is_best_answer ? "outline outline-2 outline-[var(--accent-success)]" : ""
              }`}
            >
              <div className="flex flex-wrap items-center gap-2 text-[12px]">
                <span className="font-semibold text-[var(--text-primary)]">
                  {a.responder?.display_name ?? a.responder?.username ?? "someone"}
                </span>
                {a.responder ? (
                  <TrustBadge
                    levelName={a.responder.trust_level_name}
                    stage={a.responder.trust_stage}
                    score={a.responder.reputation_score}
                    plain
                  />
                ) : null}
                {a.is_best_answer ? (
                  <span className="inline-flex items-center gap-1 rounded-[var(--radius-md)] bg-[color-mix(in_srgb,var(--accent-success)_14%,transparent)] px-2 py-0.5 font-medium text-[var(--accent-success)]">
                    <SealCheck size={12} weight="fill" /> Best answer
                  </span>
                ) : null}
                {a.is_first_responder ? (
                  <span className="inline-flex items-center gap-1 text-[var(--accent-star)]">
                    <Medal size={13} weight="fill" /> First responder
                  </span>
                ) : null}
              </div>
              <p className="mt-2 whitespace-pre-line text-[14px] leading-relaxed text-[var(--text-primary)]">
                {a.body}
              </p>
              {isAsker && !a.is_best_answer ? (
                <div className="mt-3">
                  <BestAnswerButton questionId={question.id} answerId={a.id} />
                </div>
              ) : null}
            </li>
          ))}
        </ul>

        <div className="mt-8">
          <h2 className="text-[15px] font-semibold text-[var(--text-primary)]">Your answer</h2>
          <div className="mt-3">
            <AnswerForm questionId={question.id} canAnswer={canAnswer} />
          </div>
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}
