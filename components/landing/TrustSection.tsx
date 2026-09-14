import { TRUST_POINTS } from "@/lib/landing-data";

/**
 * "Trust is expensive. We won't waste yours.", built to "Mobile Landing Page"
 * (1902:1504), read 2026-09-14.
 *
 * Phone: 40px under the rail, a 291px column centred on the page — 28px
 * SemiBold ink on its natural line, then 16px SemiBold brand orange; 20px down,
 * the points 8px apart as 20px glyphs with 10px Light text 8px after them. A
 * quiet list under a loud promise, so the glyphs are ink, not orange. From `md`
 * up there is no frame and the section takes its own screen.
 */
export function TrustSection() {
  return (
    <section className="bg-[var(--surface-app)] md:border-t md:border-[var(--border-subtle)]">
      <div className="mx-auto flex w-full max-w-[40rem] flex-col items-center px-6 pt-10 text-center md:min-h-[58vh] md:justify-center md:py-20 lg:py-28">
        <h2 className="text-[28px] font-semibold leading-[normal] text-[var(--text-primary)] lg:text-[40px]">
          Trust is expensive.
        </h2>
        <p className="text-center text-[16px] font-semibold leading-none text-[var(--accent-primary)] lg:text-[22px] lg:leading-normal">
          We won&rsquo;t waste yours.
        </p>

        <ul className="mx-auto mt-5 flex w-[291px] max-w-full flex-col gap-2 text-left lg:mt-8 lg:w-auto lg:max-w-[34rem] lg:gap-3">
          {TRUST_POINTS.map(({ icon: Icon, text }) => (
            <li key={text} className="flex items-center gap-2 lg:gap-3">
              <Icon size={20} className="shrink-0 text-[var(--text-primary)] lg:h-6 lg:w-6" />
              <span className="text-[10px] font-light leading-none text-[var(--text-primary)] lg:text-[14px] lg:leading-normal">
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
