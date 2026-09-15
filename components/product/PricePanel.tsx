import { ChartLine } from "@phosphor-icons/react/dist/ssr";

import { peso, type PricePanel as PanelData } from "@/lib/products";

/**
 * The FR-2 community price panel.
 *
 * NO FIGMA FRAME for the panel itself — the file draws only the "Price History"
 * Chip/Action that opens it (Question Page 4218:1856) — so it is set in the
 * file's card language: a white card at radius 16 with the card shadow, 20px
 * in; the ChartLine glyph of that chip 4px before the heading in 16px
 * SemiBold; figures in 20px SemiBold with 12px Light labels; notes in 12px
 * Light at 70% on 18px lines.
 *
 * Three distinct states, all of them required by the requirement rather than
 * invented: enough data, not enough data yet, and the server being unreachable.
 * The middle one is the interesting case — FR-2 says the panel is shown "only
 * when ≥ 3 independent observations exist", so below that the component says
 * how many more are needed and shows no prices at all. The API publishes none
 * below the threshold either, so there is nothing here to accidentally reveal.
 *
 * These are community observations of what real people paid, never a scraped
 * or claimed market price — the copy says so, because a range with no
 * provenance reads like a listing price and this platform's whole argument is
 * that it does not make claims it cannot back.
 */
const CARD = "rounded-[16px] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-card)]";
const NOTE = "text-[12px] font-light leading-[18px] text-[rgba(32,32,32,0.7)]";

function Heading() {
  return (
    <div className="flex items-center gap-1">
      <ChartLine size={20} aria-hidden="true" className="shrink-0 text-[var(--text-primary)]" />
      <h2 id="price-panel-heading" className="text-[16px] font-semibold leading-none text-[var(--text-primary)]">
        What people paid
      </h2>
    </div>
  );
}

export function PricePanel({
  panel,
  compact = false,
}: {
  panel: PanelData | null;
  /**
   * Drop the leading margin, for the desktop review sidebar where the column's
   * own `gap` already provides the spacing. The panel keeps its heading in both
   * cases — it is the only thing naming what the numbers are.
   */
  compact?: boolean;
}) {
  const outer = compact ? "" : "mt-8 ";
  if (panel === null) {
    return (
      <section aria-labelledby="price-panel-heading" className={`${outer}${CARD}`}>
        <Heading />
        <p className={`mt-3 ${NOTE}`}>We couldn&rsquo;t load price observations just now. They&rsquo;ll be back shortly.</p>
      </section>
    );
  }

  const needed = Math.max(0, panel.required_independent - panel.independent_count);

  return (
    <section aria-labelledby="price-panel-heading" className={`${outer}${CARD}`}>
      <Heading />

      {panel.sufficient ? (
        <>
          {/* Range first: it is the honest headline for a community sample.
              The median sits beside it rather than above it, because one
              number would read as "the price" and this is not that. */}
          <p className="mt-4 text-[20px] font-semibold leading-none text-[var(--text-primary)]">
            {peso(panel.low)} <span className="text-[var(--base-gray-400)]">–</span> {peso(panel.high)}
          </p>
          <dl className="mt-4 flex flex-wrap gap-x-6 gap-y-3">
            <div className="flex flex-col-reverse gap-1">
              <dt className="text-[12px] font-light leading-none text-[rgba(32,32,32,0.7)]">Typical</dt>
              <dd className="text-[14px] font-medium leading-none text-[var(--text-primary)]">{peso(panel.median)}</dd>
            </div>
            <div className="flex flex-col-reverse gap-1">
              <dt className="text-[12px] font-light leading-none text-[rgba(32,32,32,0.7)]">Reports</dt>
              <dd className="text-[14px] font-medium leading-none text-[var(--text-primary)]">
                {panel.observation_count} from {panel.independent_count} buyers
              </dd>
            </div>
            {panel.latest_observed_at ? (
              <div className="flex flex-col-reverse gap-1">
                <dt className="text-[12px] font-light leading-none text-[rgba(32,32,32,0.7)]">Latest</dt>
                <dd className="text-[14px] font-medium leading-none text-[var(--text-primary)]">
                  {new Date(panel.latest_observed_at).toLocaleDateString("en-PH", {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })}
                </dd>
              </div>
            ) : null}
          </dl>
          {panel.platforms.length > 0 ? (
            <p className={`mt-3 capitalize ${NOTE}`}>Seen on {panel.platforms.join(", ")}</p>
          ) : null}
          <p className={`mt-3 ${NOTE}`}>
            Prices buyers here reported paying, each checked by a moderator. Not a listing price, and never
            collected from a marketplace.
          </p>
        </>
      ) : (
        <>
          <p className="mt-3 text-[14px] leading-[21px] text-[var(--text-primary)]">
            {panel.observation_count === 0
              ? panel.pending_count > 0
                ? "No checked reports yet."
                : "Nobody has reported paying for this yet."
              : `${panel.observation_count} report${panel.observation_count === 1 ? "" : "s"} so far, from ${panel.independent_count} buyer${panel.independent_count === 1 ? "" : "s"}.`}
          </p>
          {/* Pending reports are counted, never priced: a moderator has not
              checked them, so they cannot open the range. Saying they exist
              keeps "nobody has reported" from being false. */}
          {panel.pending_count > 0 ? (
            <p className="mt-1 text-[14px] leading-[21px] text-[var(--text-primary)]">
              {panel.pending_count === 1
                ? "1 more report is waiting for a moderator to check."
                : `${panel.pending_count} more reports are waiting for a moderator to check.`}
            </p>
          ) : null}
          <p className="mt-1 text-[14px] leading-[21px] text-[var(--text-primary)]">
            {needed === 1
              ? "One more buyer and we can show a price range."
              : `${needed} more buyers and we can show a price range.`}
          </p>
          <p className={`mt-3 ${NOTE}`}>
            We wait for {panel.required_independent} independent reports so one person&rsquo;s price
            can&rsquo;t stand in for everyone&rsquo;s.
          </p>
        </>
      )}
    </section>
  );
}

export default PricePanel;
