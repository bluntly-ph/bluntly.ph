import type { Metadata } from "next";
import Link from "next/link";
import { Plus } from "@phosphor-icons/react/dist/ssr";

import { SiteFooter } from "@/components/site/SiteFooter";
import { Unavailable } from "@/components/site/Unavailable";
import { SiteHeader, type HeaderUser } from "@/components/site/SiteHeader";
import { QuestionResultRow } from "@/components/search/QuestionResultRow";
import { getUser } from "@/lib/dal";
import { getQuestions } from "@/lib/qa";

export const metadata: Metadata = {
  title: "Ask the community — bluntly",
};

/**
 * Every open question. NO FIGMA FRAME for this list — the file draws questions
 * only per product ("Question Page", 4218:1856) and in search — so it is built
 * from those parts: the page title in 20px SemiBold, "Ask a question" as a
 * Chip/Action (7166:4933: 32px, a dark 1px outline at radius 16, a 20px glyph
 * 4px before 12px Light), and each question as the search tab's
 * QuestionPreviewCard between full-bleed hairlines.
 */
export default async function QuestionsPage() {
  // Parallel: the viewer and the list are independent (see app/page.tsx).
  const [me, questions] = await Promise.all([getUser().catch(() => null), getQuestions()]);
  const user: HeaderUser = me ? { username: me.username, avatarUrl: me.avatar_url } : null;

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={user} />
      <main className="mx-auto w-full max-w-[42rem] flex-1 pb-16 pt-5 md:px-6">
        <div className="flex flex-wrap items-start justify-between gap-3 px-4 md:px-0">
          <div>
            <h1 className="text-[20px] font-semibold leading-[30px] text-[var(--text-primary)]">
              Ask the community
            </h1>
            <p className="mt-1 text-[12px] font-light leading-[18px] text-[rgba(32,32,32,0.7)]">
              Real answers from people who actually bought it — before you do.
            </p>
          </div>
          <Link
            href="/questions/new"
            className="inline-flex h-8 shrink-0 items-center gap-1 rounded-[16px] border border-[var(--text-primary)] px-[11px] text-[12px] font-light leading-none text-[var(--text-primary)] no-underline hover:border-[var(--accent-primary)] hover:text-[var(--accent-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-primary)]"
          >
            <Plus size={20} weight="light" aria-hidden="true" />
            Ask a question
          </Link>
        </div>

        {questions === null ? (
          <div className="px-4 md:px-0">
            <Unavailable what="questions" />
          </div>
        ) : questions.length > 0 ? (
          <ul className="mt-5 border-t border-[var(--line-hairline-10)]">
            {questions.map((q) => (
              <QuestionResultRow key={q.id} question={q} />
            ))}
          </ul>
        ) : (
          <div className="mt-5 border-t border-[var(--line-hairline-10)] px-4 pt-10 text-center md:px-0">
            <p className="text-[16px] leading-none tracking-[0.8px] text-[var(--text-primary)]">No questions yet</p>
            <p className="mt-[9px] text-[12px] font-light leading-[18px] text-[rgba(32,32,32,0.7)]">
              Be the first to ask the community.
            </p>
          </div>
        )}
      </main>
      <SiteFooter />
    </div>
  );
}
