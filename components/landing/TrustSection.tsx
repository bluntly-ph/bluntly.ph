import { TRUST_POINTS } from "@/lib/landing-data";

/**
 * "Trust is expensive. We won't waste yours." — a calm, centered screen.
 *
 * Aligned to the frame (BUG-007). It sat on its own white band, which broke the
 * continuous neutral ground the sections above it share; the headings were a
 * size and weight larger than drawn; and the bullet icons were accent orange,
 * which read as four calls to action rather than a list of facts. The bullet
 * column is narrower than the section so the lines break where the frame breaks
 * them instead of running the full width.
 */
export function TrustSection() {
  return (
    <section className="border-t border-[var(--border-subtle)] bg-[var(--surface-app)]">
      <div className="mx-auto flex min-h-[58vh] w-full max-w-[40rem] flex-col items-center justify-center px-6 py-20 text-center lg:py-28">
        {/* Both lines are SemiBold in the frame — 28px ink, then 16px brand
            orange, centred. The bullets are 10px Light with 20px icons and 8px
            gaps, a deliberately quiet list under a loud promise. */}
        <h2 className="text-[28px] font-semibold leading-[normal] text-[var(--text-primary)] lg:text-[40px]">
          Trust is expensive.
        </h2>
        <p className="text-center text-[16px] font-semibold text-[var(--accent-primary)] lg:text-[22px]">
          We won&rsquo;t waste yours.
        </p>

        {/* The bullet column is deliberately narrow at 390px — that is the
            frame. Left at 18rem it became a thin ribbon stranded in a 1280
            canvas, so it widens with the viewport while the mobile proportions
            stay exactly as drawn. */}
        <ul className="mx-auto mt-5 flex max-w-[18rem] flex-col gap-2 text-left lg:mt-8 lg:max-w-[34rem] lg:gap-3">
          {TRUST_POINTS.map(({ icon: Icon, text }) => (
            <li key={text} className="flex items-center gap-2 lg:gap-3">
              <Icon
                size={20}
                weight="regular"
                className="shrink-0 text-[var(--text-primary)] lg:h-6 lg:w-6"
              />
              <span className="text-[10px] font-light tracking-[0.12px] text-[var(--text-primary)] lg:text-[14px]">
                {text}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export default TrustSection;
