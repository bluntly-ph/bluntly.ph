import { TRUST_POINTS } from "@/lib/landing-data";

/**
 * "Trust is expensive. We won't waste yours." — a calm, centered screen on its
 * own white band so the promise stands apart from the busier sections.
 */
export function TrustSection() {
  return (
    <section className="border-t border-[var(--border-subtle)] bg-[var(--surface-card)]">
      <div className="mx-auto flex min-h-[58vh] w-full max-w-[40rem] flex-col items-center justify-center px-6 py-20 text-center lg:py-28">
        <h2 className="text-[30px] font-bold leading-tight text-[var(--text-primary)] lg:text-[40px]">
          Trust is expensive.
        </h2>
        <p className="mt-2 text-[20px] font-semibold text-[var(--accent-primary)] lg:text-[26px]">
          We won&rsquo;t waste yours.
        </p>

        <ul className="mx-auto mt-10 flex max-w-[26rem] flex-col gap-5 text-left">
          {TRUST_POINTS.map(({ icon: Icon, text }) => (
            <li key={text} className="flex items-center gap-3">
              <Icon
                size={22}
                weight="regular"
                className="shrink-0 text-[var(--accent-primary)]"
              />
              <span className="text-[15px] text-[var(--text-secondary)]">{text}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export default TrustSection;
