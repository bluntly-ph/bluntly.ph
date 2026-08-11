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
        <h2 className="text-[28px] font-semibold leading-tight text-[var(--text-primary)]">
          Trust is expensive.
        </h2>
        <p className="mt-2 text-[16px] font-semibold text-[var(--accent-primary)]">
          We won&rsquo;t waste yours.
        </p>

        <ul className="mx-auto mt-10 flex max-w-[20rem] flex-col gap-5 text-left">
          {TRUST_POINTS.map(({ icon: Icon, text }) => (
            <li key={text} className="flex items-center gap-3">
              <Icon
                size={22}
                weight="regular"
                className="shrink-0 text-[var(--text-primary)]"
              />
              <span className="text-[13px] leading-relaxed text-[var(--text-secondary)]">
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
