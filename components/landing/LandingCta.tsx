import Image from "next/image";
import Link from "next/link";
import { ArrowRight } from "@phosphor-icons/react/dist/ssr";

/**
 * The "Stop guessing. Start knowing." card, built to "Mobile Landing Page"
 * (1902:1504), read 2026-09-14.
 *
 * Phone: 40px under the trust list, a 358x268 brand card at radius 12 carrying
 * the frame's two decorative ellipses (#de8463 at 20%, exported as assets).
 * "READY?" in 12px Regular 16px down; "Stop guessing." in 24px Regular and
 * "Start knowing." in 20px italic on their natural lines; the invitation in
 * 12px Light on an 18px line within 326px; then two 42px pills right-aligned
 * 20px from the card edge — "Find a review" on --surface-app with a 16px brand
 * arrow, and "Write & Earn" outlined — both 12px Light.
 *
 * The frame's own footer overlaps this card, a layout slip in the artwork, so
 * the card keeps 40px clear above the footer instead.
 */
export function LandingCta() {
  return (
    <section className="bg-[var(--surface-app)] md:border-t md:border-[var(--border-subtle)]">
      <div className="mx-auto flex w-full max-w-[72rem] items-center px-4 pb-10 pt-10 sm:px-6 md:py-16 lg:min-h-[60vh] lg:px-10 lg:py-24">
        <div className="relative w-full overflow-hidden rounded-[12px] bg-[var(--accent-primary)] px-4 pb-[42px] pt-4 text-[var(--text-on-brand)] md:px-10 md:py-12 lg:px-14 lg:py-16">
          <Image
            src="/figma/landing/cta-ellipse-90.svg"
            alt=""
            aria-hidden="true"
            width={170}
            height={119}
            unoptimized
            className="pointer-events-none absolute left-[21px] top-[149px] h-[119px] w-[170px]"
          />
          <Image
            src="/figma/landing/cta-ellipse-91.svg"
            alt=""
            aria-hidden="true"
            width={163}
            height={56}
            unoptimized
            className="pointer-events-none absolute left-[185px] top-0 h-14 w-[163px]"
          />

          <div className="relative max-w-[40rem]">
            <span className="block pl-[3px] text-[12px] leading-none md:pl-0">READY?</span>
            <h2 className="mt-[14px] font-normal text-white">
              <span className="block text-[24px] leading-[36px]">Stop guessing.</span>
              <span className="block text-[20px] italic leading-[30px]">Start knowing.</span>
            </h2>
            <p className="mt-3 max-w-[326px] text-[12px] font-light leading-[18px] md:max-w-[32rem] md:text-[15px] md:leading-normal">
              Join Filipinos making smarter purchases and the reviewers earning from
              honest opinions.
            </p>

            <div className="mt-7 flex flex-wrap justify-end gap-2 pr-1 md:justify-start md:pr-0">
              <Link
                href="/search"
                className="inline-flex h-[42px] items-center gap-3 rounded-[32px] bg-[var(--surface-app)] pl-4 pr-[13px] text-[12px] font-light leading-none text-[var(--text-primary)] no-underline hover:bg-white"
              >
                Find a review
                <ArrowRight size={16} className="text-[var(--accent-primary)]" />
              </Link>
              <Link
                href="/reviews/new"
                className="inline-flex h-[42px] items-center rounded-[32px] border border-[var(--text-on-brand)] px-4 text-[12px] font-light leading-none text-[var(--text-on-brand)] no-underline hover:bg-white/10"
              >
                Write &amp; Earn
              </Link>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

export default LandingCta;
