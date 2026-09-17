import { Fire } from "@phosphor-icons/react/dist/ssr";

import type { ContributionStreak } from "@/lib/dashboard";

/**
 * The contribution streak on Insights: a flame, a day count, and a month grid
 * of filled dots.
 *
 * Owner decision, 2026-08-27: this counts days the reviewer CONTRIBUTED — a
 * published review, a question, an answer, or a price observation — never days
 * they visited. Every filled dot is a real date from data the application
 * already stores.
 *
 * Set as a dashboard card (see app/dashboard/insights/page.tsx for why there is
 * no frame to follow): white, radius 12, the 0 4 2 25% drop shadow, a 16px
 * glyph before a 12px Medium title with the month in 10px Light at the right,
 * the count in 20px SemiBold as History's income card sets a figure, and the
 * explanation in 10px Light at 70%.
 *
 * The grid is decorative and marked `aria-hidden`, because colour alone must
 * not carry the information. The same facts are stated in words: visibly in
 * the summary line, and in full — every active date — for screen readers.
 */
export function StreakCard({ streak }: { streak: ContributionStreak | null }) {
  const days = streak?.current_streak ?? 0;
  const cells = streak?.calendar ?? [];
  const activeDates = cells.filter((c) => c.contributed).map((c) => c.day);

  const monthName = streak
    ? new Date(`${streak.calendar_month}T00:00:00`).toLocaleDateString("en-PH", {
        month: "long",
        year: "numeric",
      })
    : "";

  const dayNumber = (iso: string) => Number(iso.slice(8, 10));
  const spoken = (iso: string) =>
    new Date(`${iso}T00:00:00`).toLocaleDateString("en-PH", {
      month: "long",
      day: "numeric",
    });

  return (
    <section
      aria-labelledby="streak-heading"
      className="mx-4 rounded-[12px] bg-[var(--surface-card)] px-6 pb-6 pt-4 [filter:drop-shadow(0_4px_2px_rgba(0,0,0,0.25))] lg:mx-0"
    >
      <div className="flex items-center justify-between">
        <h2
          id="streak-heading"
          className="flex items-center gap-1 text-[12px] font-medium leading-none text-[var(--text-primary)]"
        >
          <Fire size={16} weight="regular" />
          Streak
        </h2>
        <span className="text-[10px] font-light leading-none text-[var(--text-primary)]">{monthName}</span>
      </div>

      {!streak ? (
        <p className="mt-5 text-[12px] text-[var(--text-secondary)]">
          Unable to load your streak right now.
        </p>
      ) : (
        <div className="mt-5 flex items-center gap-6">
          <div className="shrink-0 text-center">
            <Fire
              size={40}
              weight="fill"
              aria-hidden
              className={days > 0 ? "mx-auto text-[var(--accent-primary)]" : "mx-auto text-[var(--line-hairline-30)]"}
            />
            <p className="mt-2 text-[20px] font-semibold leading-none text-[var(--text-primary)] [font-variant-numeric:tabular-nums]">
              {days}
              <span className="ml-1 text-[12px] font-light">{days === 1 ? "day" : "days"}</span>
            </p>
          </div>

          {/* Decorative. The words below carry the same information. */}
          <div aria-hidden className="grid max-w-[13rem] flex-1 grid-cols-7 gap-1.5">
            {cells.map((cell) => (
              <span
                key={cell.day}
                title={`${spoken(cell.day)}: ${cell.contributed ? "contributed" : "nothing"}`}
                className={`aspect-square rounded-full ${
                  cell.contributed ? "bg-[var(--accent-primary)]" : "bg-[#f2f2f2]"
                }`}
              >
                <span className="sr-only">{dayNumber(cell.day)}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {streak ? (
        <>
          <p className="mt-5 text-[10px] font-light leading-[15px] text-[rgba(32,32,32,0.7)]">
            {days === 0
              ? "No current streak. Publish a review, ask or answer a question, or add a price you paid, and your streak starts today."
              : `${days} ${days === 1 ? "day" : "days"} in a row. ${
                  streak.active_today ? "Today already counts." : "Contribute today to keep it going."
                }`}{" "}
            Counted from what you contribute &mdash; reviews, questions, answers and prices &mdash; not
            from visits.
          </p>

          {/* The grid's meaning, in words, for anyone who cannot see colour. */}
          <p className="sr-only">
            {activeDates.length === 0
              ? `No contributions recorded in ${monthName}.`
              : `Contributed on ${activeDates.length} ${
                  activeDates.length === 1 ? "day" : "days"
                } in ${monthName}: ${activeDates.map(spoken).join(", ")}.`}
          </p>
        </>
      ) : null}
    </section>
  );
}
