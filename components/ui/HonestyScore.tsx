import { Shield } from "@phosphor-icons/react/dist/ssr";

import { trustDescription, trustLevel, trustScore } from "@/lib/trust";

/**
 * The Honesty Score badge, Figma component "HonestyScore" (6956:911): a 16px
 * Phosphor Shield in the trust blue and the reviewer's 0-100 score in 12px
 * Poppins Light, 4px apart.
 *
 * The file distinguishes it from the trust stage (Newcomer to Community
 * Expert), which is a separate ladder with its own mark, so the level name is
 * not drawn here. It stays in the accessible name, where the bare number would
 * otherwise be an orphan.
 *
 * Renders nothing without a score: a shield with no number says nothing.
 */
export function HonestyScore({
  score,
  levelName,
  stage,
}: {
  score: string | number | null | undefined;
  levelName?: string | null;
  stage?: number | null;
}) {
  const value = trustScore(score);
  if (value === null) return null;
  const description = trustDescription(trustLevel(levelName, stage), value);

  return (
    <span role="img" aria-label={description} title={description} className="inline-flex shrink-0 items-center gap-1">
      <Shield size={16} weight="fill" aria-hidden="true" className="text-[var(--accent-trust)]" />
      <span aria-hidden="true" className="text-[12px] font-light leading-none text-[var(--text-primary)]">
        {value}
      </span>
    </span>
  );
}

export default HonestyScore;
