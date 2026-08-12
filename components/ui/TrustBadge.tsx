import { ShieldCheck } from "@phosphor-icons/react/dist/ssr";

import { trustDescription, trustLevel, trustScore } from "@/lib/trust";

/**
 * The reviewer trust badge — level name and numeric score together (BUG-004).
 *
 * `plain` drops the chip background for places that sit inside a denser row
 * (the featured card, a comment byline) where a filled pill would compete with
 * the name next to it.
 */
export function TrustBadge({
  levelName,
  stage,
  score,
  plain = false,
  className = "",
}: {
  levelName: string | null | undefined;
  stage?: number | null;
  score: string | number | null | undefined;
  plain?: boolean;
  className?: string;
}) {
  const level = trustLevel(levelName, stage);
  const value = trustScore(score);
  const description = trustDescription(level, value);

  return (
    <span
      // The whole badge is one label: read as a unit, the parts are a sentence;
      // read separately, "62" is an orphan number next to a name.
      aria-label={description}
      title={description}
      className={[
        "inline-flex shrink-0 items-center gap-1 text-[12px] font-medium text-[var(--accent-trust)]",
        plain
          ? ""
          : "rounded-[var(--radius-pill)] bg-[color-mix(in_srgb,var(--accent-trust)_12%,transparent)] px-3 py-1",
        className,
      ].join(" ")}
    >
      <ShieldCheck size={14} weight="fill" aria-hidden="true" />
      <span aria-hidden="true">
        {level}
        {value === null ? null : (
          <>
            <span className="mx-1 opacity-50">·</span>
            {value}
          </>
        )}
      </span>
    </span>
  );
}

export default TrustBadge;
