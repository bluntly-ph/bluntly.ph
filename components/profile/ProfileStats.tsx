import Image from "next/image";
import { Cloud } from "@phosphor-icons/react/dist/ssr";

import { Unavailable } from "@/components/site/Unavailable";
import type { TrustProfile } from "@/lib/trust-data";

/**
 * The Stats tab of a profile: Figma "Profile Page - Stats" (5446:6532), read
 * 2026-09-16.
 *
 * The frame is the mascot in a 96x154 block 20px under the tab rule, four
 * Icon/Cloud glyphs around it, and a white card — 358 wide, radius 12, 24px in,
 * shadow 0 4px 2px at 10% — holding the level name, a "Level n" chip, the next
 * step in 12px Light on a 1.5 line, an 8px progress bar at radius 12, and a 10px
 * caption at 40% ink.
 *
 * WHAT THE NUMBERS ARE. Every figure is the account's own, served by
 * `GET /users/{id}/trust`: the level name and stage are the database's, and the
 * bar is `reviews_have / reviews_needed` from the trust ladder itself
 * (`app/services/trust.py`). The frame's own placeholders disagree with each
 * other — its card is titled "Contributor" while its body invites the reader to
 * *become* one, and its caption promises "Trusted" for a level the ladder calls
 * "Trusted Reviewer" — so the copy here is generated from the real ladder
 * instead of transcribed. That is an INTENTIONAL PRODUCT DIFFERENCE.
 *
 * NOT DRAWN: the frame's second card, "Frequent Interactions", showing three
 * overlapping avatars. Nothing in the product records who a member interacts
 * with — there is no follow graph, no interaction count, and no endpoint — so
 * the card would be three invented faces. Classified MISSING — NO DATA SOURCE
 * in the feature matrix rather than faked here.
 */

/** The frame's four clouds, in its 390px frame coordinates, relative to the tab rule. */
const CLOUDS: { left: number; top: number; size: number; flip?: boolean }[] = [
  { left: 16, top: 57, size: 32 },
  { left: 46, top: 15, size: 64 },
  { left: 289, top: 57, size: 32 },
  { left: 323, top: 35, size: 32, flip: true },
];

function StatsDecor() {
  return (
    <span
      aria-hidden="true"
      className="pointer-events-none absolute inset-x-0 top-0 -z-10 block h-[190px] select-none md:left-1/2 md:right-auto md:w-[390px] md:-translate-x-1/2"
    >
      {CLOUDS.map((c, i) => (
        <Cloud
          key={i}
          size={c.size}
          weight="thin"
          className={`absolute text-[rgba(239,88,33,0.2)] ${c.flip ? "rotate-180" : ""}`}
          style={{ left: c.left, top: c.top }}
        />
      ))}
    </span>
  );
}

export function ProfileStats({ trust }: { trust: TrustProfile | null }) {
  if (trust === null) {
    return (
      <div className="px-4 md:px-0">
        <Unavailable what="your stats" />
      </div>
    );
  }

  const progress = trust.progress;
  const pct = progress
    ? Math.min(100, Math.round((progress.reviews_have / progress.reviews_needed) * 100))
    : 100;

  return (
    <div className="relative isolate pb-10">
      <StatsDecor />

      {/* 96x154 in the frame; the artwork's own ratio gives the width. */}
      <div className="flex justify-center pt-[20px]">
        <Image
          src="/mascots/bunbun-neutral.svg"
          alt=""
          aria-hidden="true"
          width={96}
          height={154}
          className="h-[154px] w-auto select-none"
        />
      </div>

      <div className="mx-auto mt-[-30px] w-full max-w-[358px] px-4 md:px-0">
        <section className="rounded-[12px] bg-[var(--surface-card)] p-6 shadow-[0_4px_2px_rgba(0,0,0,0.1)]">
          <div className="flex items-start justify-between gap-3">
            <h2 className="text-[16px] font-medium leading-none text-[var(--text-primary)]">
              {trust.trust_level_name}
            </h2>
            <span className="rounded-[8px] bg-[rgba(239,88,33,0.1)] px-2 py-[6px] text-[10px] leading-none text-[var(--accent-primary)] opacity-80">
              Level {trust.trust_stage}
            </span>
          </div>

          {progress ? (
            <div className="mt-4 flex flex-col gap-3">
              <p className="text-[12px] font-light leading-[1.5] text-[var(--text-primary)]">
                {nextStepLine(progress.next_stage, progress.next_level_name)}
              </p>
              <div
                className="h-2 w-full overflow-hidden rounded-[12px] bg-[rgba(240,238,233,0.91)]"
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={progress.reviews_needed}
                aria-valuenow={progress.reviews_have}
                aria-label={`Progress to ${progress.next_level_name}`}
              >
                <div
                  className="h-2 rounded-[12px] bg-[var(--accent-primary)]"
                  style={{ width: `${pct}%` }}
                />
              </div>
              <p className="text-[10px] leading-none text-[rgba(32,32,32,0.4)]">
                {progress.reviews_have} of {progress.reviews_needed}{" "}
                {progress.next_stage === 1 ? "review" : "verified reviews"} to become{" "}
                {progress.next_level_name}
              </p>
            </div>
          ) : (
            <p className="mt-4 text-[12px] font-light leading-[1.5] text-[var(--text-primary)]">
              You are at the top of the ladder. Keep reviewing honestly — nothing
              above {trust.trust_level_name} is waiting to be unlocked.
            </p>
          )}
        </section>

        {/* The figures the header already shows are not repeated here; these are
            the two the header has no room for, and both are served. */}
        <dl className="mt-4 grid grid-cols-2 gap-4">
          <div className="rounded-[12px] bg-[var(--surface-card)] p-6 shadow-[0_4px_2px_rgba(0,0,0,0.1)]">
            <dt className="text-[12px] font-light leading-none text-[rgba(32,32,32,0.7)]">
              Helpfulness
            </dt>
            <dd className="mt-3 text-[16px] font-semibold leading-none text-[var(--accent-primary)]">
              {Math.round(Number(trust.helpfulness_ratio) || 0)}
              <span className="text-[12px] font-light text-[var(--text-primary)]">/100</span>
            </dd>
          </div>
          <div className="rounded-[12px] bg-[var(--surface-card)] p-6 shadow-[0_4px_2px_rgba(0,0,0,0.1)]">
            <dt className="text-[12px] font-light leading-none text-[rgba(32,32,32,0.7)]">
              Badges earned
            </dt>
            <dd className="mt-3 text-[16px] font-semibold leading-none text-[var(--accent-primary)]">
              {trust.badges.length}
            </dd>
          </div>
        </dl>

        {trust.badges.length > 0 ? (
          <ul className="mt-4 flex flex-wrap gap-2">
            {trust.badges.map((badge) => (
              <li
                key={badge.badge_id}
                className="rounded-[8px] bg-[rgba(239,88,33,0.1)] px-2 py-[6px] text-[10px] leading-none text-[var(--accent-primary)]"
              >
                {badge.name}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  );
}

/**
 * What the member has to do next, said in one line.
 *
 * Generated from the stage rather than stored as copy per level, because the
 * thresholds live in the backend ladder and the wording only differs where the
 * requirement itself differs: stage 1 counts any published review, stage 2 wants
 * proof of purchase, and everything above wants volume and a helpfulness record.
 */
function nextStepLine(nextStage: number, nextLevel: string): string {
  if (nextStage === 1) return `Publish your first review to become a ${nextLevel}.`;
  if (nextStage === 2)
    return `Add proof of purchase to a review to become a ${nextLevel} and unlock earnings.`;
  return `Keep publishing verified reviews that readers find helpful to become ${nextLevel}.`;
}

export default ProfileStats;
