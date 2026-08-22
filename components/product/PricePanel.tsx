import { Tag } from "@phosphor-icons/react/dist/ssr";

import { peso, type PricePanel as PanelData } from "@/lib/products";

/**
 * The FR-2 community price panel.
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
      <section
        aria-labelledby="price-panel-heading"
        className={`${outer}rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-hairline-inset)]`}
      >
        <h2 id="price-panel-heading" className="text-[15px] font-semibold text-[var(--text-primary)]">
          What people paid
        </h2>
        <p className="mt-1 text-[13px] text-[var(--text-secondary)]">
          We couldn&rsquo;t load price observations just now. They&rsquo;ll be
          back shortly.
        </p>
      </section>
    );
  }

  const needed = Math.max(0, panel.required_independent - panel.independent_count);

  return (
    <section
      aria-labelledby="price-panel-heading"
      className={`${outer}rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-5 shadow-[var(--shadow-hairline-inset)]`}
    >
      <div className="flex items-center gap-2">
        <Tag size={18} weight="fill" className="text-[var(--accent-primary)]" aria-hidden="true" />
        <h2 id="price-panel-heading" className="text-[15px] font-semibold text-[var(--text-primary)]">
          What people paid
        </h2>
      </div>

      {panel.sufficient ? (
        <>
          {/* Range first: it is the honest headline for a community sample.
              The median sits beside it rather than above it, because one
              number would read as "the price" and this is not that. */}
          <p className="mt-3 text-[24px] font-bold leading-tight text-[var(--text-primary)]">
            {peso(panel.low)} <span className="text-[var(--text-secondary)]">–</span>{" "}
            {peso(panel.high)}
          </p>
          <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1 text-[13px]">
            <div className="flex gap-1.5">
              <dt className="text-[var(--text-secondary)]">Typical</dt>
              <dd className="font-medium text-[var(--text-primary)]">{peso(panel.median)}</dd>
            </div>
            <div className="flex gap-1.5">
              <dt className="text-[var(--text-secondary)]">Reports</dt>
              <dd className="font-medium text-[var(--text-primary)]">
                {panel.observation_count} from {panel.independent_count} buyers
              </dd>
            </div>
            {panel.latest_observed_at ? (
              <div className="flex gap-1.5">
                <dt className="text-[var(--text-secondary)]">Latest</dt>
                <dd className="font-medium text-[var(--text-primary)]">
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
            <p className="mt-2 text-[12px] capitalize text-[var(--text-muted)]">
              Seen on {panel.platforms.join(", ")}
            </p>
          ) : null}
          <p className="mt-3 text-[12px] text-[var(--text-muted)]">
            Prices buyers here reported paying. Not a listing price, and never
            collected from a marketplace.
          </p>
        </>
      ) : (
        <>
          <p className="mt-2 text-[13px] text-[var(--text-secondary)]">
            {panel.observation_count === 0
              ? "Nobody has reported paying for this yet."
              : `${panel.observation_count} report${panel.observation_count === 1 ? "" : "s"} so far, from ${panel.independent_count} buyer${panel.independent_count === 1 ? "" : "s"}.`}
          </p>
          <p className="mt-1 text-[13px] text-[var(--text-secondary)]">
            {needed === 1
              ? "One more buyer and we can show a price range."
              : `${needed} more buyers and we can show a price range.`}
          </p>
          <p className="mt-3 text-[12px] text-[var(--text-muted)]">
            We wait for {panel.required_independent} independent reports so one
            person&rsquo;s price can&rsquo;t stand in for everyone&rsquo;s.
          </p>
        </>
      )}
    </section>
  );
}

export default PricePanel;
