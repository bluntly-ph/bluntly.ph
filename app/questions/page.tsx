import type { Metadata } from "next";
import Link from "next/link";
import { ChatCircle, PlusCircle, SealCheck } from "@phosphor-icons/react/dist/ssr";

import { SiteFooter } from "@/components/site/SiteFooter";
import { Unavailable } from "@/components/site/Unavailable";
import { SiteHeader, type HeaderUser } from "@/components/site/SiteHeader";
import { Button } from "@/components/ui/Button";
import { getUser } from "@/lib/dal";
import { getQuestions } from "@/lib/qa";

export const metadata: Metadata = {
  title: "Ask the community — bluntly",
};

export default async function QuestionsPage() {
  // Parallel: the viewer and the list are independent (see app/page.tsx).
  const [me, questions] = await Promise.all([
    getUser().catch(() => null),
    getQuestions(),
  ]);
  const user: HeaderUser = me
    ? { username: me.username, avatarUrl: me.avatar_url }
    : null;

  return (
    <div className="flex min-h-dvh flex-col bg-[var(--surface-app)]">
      <SiteHeader user={user} />
      <main className="mx-auto w-full max-w-[52rem] flex-1 px-6 py-8 lg:py-10">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-[24px] font-bold text-[var(--text-primary)]">
              Ask the community
            </h1>
            <p className="mt-1 text-[14px] text-[var(--text-secondary)]">
              Real answers from people who actually bought it — before you do.
            </p>
          </div>
          <Link href="/questions/new" className="contents">
            <Button size="sm" icon={<PlusCircle size={16} weight="fill" />}>
              Ask a question
            </Button>
          </Link>
        </div>

        {questions === null ? (
          <Unavailable what="questions" />
        ) : questions.length > 0 ? (
          <ul className="mt-6 flex flex-col gap-3">
            {questions.map((q) => (
              <li key={q.id}>
                <Link
                  href={`/questions/${q.id}`}
                  className="block rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-4 shadow-[var(--shadow-card)] outline outline-1 outline-transparent transition-[outline-color] hover:outline-[var(--line-hairline-10)]"
                >
                  <h2 className="text-[15px] font-semibold text-[var(--text-primary)]">
                    {q.body}
                  </h2>
                  <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-[var(--text-muted)]">
                    {q.product_name ? (
                      <span className="text-[var(--text-secondary)]">{q.product_name}</span>
                    ) : null}
                    <span className="inline-flex items-center gap-1">
                      <ChatCircle size={13} /> {q.answer_count} answer
                      {q.answer_count === 1 ? "" : "s"}
                    </span>
                    {q.best_answer_id ? (
                      <span className="inline-flex items-center gap-1 text-[var(--accent-success)]">
                        <SealCheck size={13} weight="fill" /> answered
                      </span>
                    ) : null}
                    {q.asker ? (
                      <span className="ml-auto">
                        asked by {q.asker.display_name ?? q.asker.username ?? "someone"}
                      </span>
                    ) : null}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <div className="mt-6 rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-10 text-center shadow-[var(--shadow-hairline-inset)]">
            <p className="text-[15px] font-semibold text-[var(--text-primary)]">
              No questions yet
            </p>
            <p className="mt-1 text-[14px] text-[var(--text-secondary)]">
              Be the first to ask the community.
            </p>
          </div>
        )}
      </main>
      <SiteFooter />
    </div>
  );
}
