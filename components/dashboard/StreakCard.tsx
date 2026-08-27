import { Fire } from "@phosphor-icons/react/dist/ssr";

import type { ContributionStreak } from "@/lib/dashboard";

/**
 * The Streak block of frame 5762:752: a flame, a day count, and a month grid
 * of filled dots.
 *
 * Owner decision, 2026-08-27: this counts days the reviewer CONTRIBUTED — a
 * published review, a question, an answer, or a price observation — never days
 * they visited. Every filled dot is a real date from data the application
 * already stores; the frame's "6 days" is a sample and is never rendered
 * unless the reviewer actually has six.
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
    <section aria-labelledby="streak-heading">
      <div className="flex items-baseline justify-between">
        <h2 id="streak-heading" className="text-[13px] font-semibold text-[var(--text-primary)]">
          Streak
        </h2>
        <span className="text-[12px] text-[var(--text-secondary)]">{monthName}</span>
      </div>

      {!streak ? (
        <p className="mt-3 text-[13px] text-[var(--text-secondary)]">
          Unable to load your streak right now.
        </p>
      ) : (
        <div className="mt-4 flex items-start gap-6">
          <div className="shrink-0 text-center">
            <Fire
              size={38}
              weight="fill"
              aria-hidden
              className={days > 0 ? "text-[var(--accent-primary)]" : "text-[var(--text-muted)]"}
            />
            <p className="mt-1 text-[15px] font-bold text-[var(--text-primary)] [font-variant-numeric:tabular-nums]">
              {days} {days === 1 ? "day" : "days"}
            </p>
          </div>

          {/* Decorative. The words below carry the same information. */}
          <div
            aria-hidden
            className="grid flex-1 grid-cols-7 gap-1.5"
            style={{ maxWidth: "13rem" }}
          >
            {cells.map((cell) => (
              <span
                key={cell.day}
                title={`${spoken(cell.day)}: ${cell.contributed ? "contributed" : "nothing"}`}
                className={`aspect-square rounded-full ${
                  cell.contributed
                    ? "bg-[var(--accent-primary)]"
                    : "bg-[var(--line-hairline-10)]"
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
          <p className="mt-4 text-[12px] leading-relaxed text-[var(--text-secondary)]">
            {days === 0
              ? "No current streak. Publish a review, ask or answer a question, or add a price you paid, and your streak starts today."
              : `${days} ${days === 1 ? "day" : "days"} in a row. ${
                  streak.active_today
                    ? "Today already counts."
                    : "Contribute today to keep it going."
                }`}{" "}
            Counted from what you contribute &mdash; reviews, questions,
            answers and prices &mdash; not from visits.
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
