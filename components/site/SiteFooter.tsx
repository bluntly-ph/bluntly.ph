import Link from "next/link";
import { RedditLogo } from "@phosphor-icons/react/dist/ssr";

import { Logo } from "@/components/ui/Logo";
import { FOOTER_LINKS } from "@/lib/landing-data";

/**
 * bluntly's own profiles (BUG-002, QA-005).
 *
 * These were network homepages until BUG-002 — a "Follow us" icon that drops
 * you on reddit.com follows nobody. They were then pointed at `/bluntlyph`
 * handles on four networks, and QA-005 found the obvious next problem: none of
 * those accounts exists, so all four icons lead to a 404. A dead link under
 * "Follow us" is worse than no link; it reads as an abandoned product.
 *
 * The list is therefore EMPTY until the accounts are real, and the whole block
 * hides itself when it is empty. Add an entry the day an account exists and the
 * design comes back with it — re-import that network's icon from
 * `@phosphor-icons/react/dist/ssr` and nothing else needs changing. `RedditLogo`
 * stays imported only because it types the list.
 */
const SOCIALS: { label: string; href: string; Icon: typeof RedditLogo }[] = [
  // { label: "Reddit", href: "https://www.reddit.com/r/bluntlyph", Icon: RedditLogo },
  // { label: "Instagram", href: "https://www.instagram.com/bluntlyph", Icon: InstagramLogo },
  // { label: "Facebook", href: "https://www.facebook.com/bluntlyph", Icon: FacebookLogo },
  // { label: "TikTok", href: "https://www.tiktok.com/@bluntlyph", Icon: TiktokLogo },
];

/** The frame's footer ink: #202020 at 60%. */
const INK_60 = "text-[rgba(32,32,32,0.6)]";

/**
 * The site footer, built to Figma "Footer" (6884:860), read 2026-09-14.
 *
 * Phone: --base-gray-200 (#d9d9d9); the wordmark 29px down and 24px in; 31px
 * below it two columns at x24 and x212 — "About" and "Read" in 12px Bold at 60%
 * ink, their links in 12px Light at 60% on a 26px pitch starting 16px under the
 * heading; the copyright in 12px Regular at 60%.
 *
 * INTENTIONAL PRODUCT DIFFERENCES:
 *  - The frame sets "bluntly" as bold type beside a small mark; the owner's
 *    wordmark replaced that artwork everywhere else, so it stands here too.
 *  - "Follow us" and its four icons are not drawn while no account exists
 *    (QA-005, above), so the copyright takes their place 46px under the links.
 *  - "Community Guidelines" is where the frame writes "User Agreement": it is
 *    the page the product has.
 */
export function SiteFooter() {
  return (
    <footer className="mt-4 bg-[var(--base-gray-200)]">
      <div className="mx-auto grid w-full max-w-[72rem] grid-cols-[188px_1fr] px-6 pt-[29px] sm:grid-cols-2 md:gap-10 md:py-12 lg:grid-cols-4 lg:px-10">
        <div className="col-span-2 flex lg:col-span-1">
          <span className="flex text-[var(--accent-primary)]">
            <Logo height={24} label="bluntly" />
          </span>
        </div>

        <FooterColumn title="About" links={FOOTER_LINKS.about} />
        <FooterColumn title="Read" links={FOOTER_LINKS.read} />

        {SOCIALS.length > 0 ? (
          <div className="col-span-2 mt-[46px] md:col-span-1 md:mt-0">
            <h3 className={`text-[12px] font-bold leading-[18px] ${INK_60} md:text-[13px] md:font-semibold md:text-[var(--text-primary)]`}>
              Follow us
            </h3>
            <ul className="mt-4 flex gap-4">
              {SOCIALS.map(({ label, href, Icon }) => (
                <li key={label}>
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={label}
                    className="grid h-9 w-9 place-items-center rounded-full text-[var(--text-primary)] hover:bg-[var(--line-hairline-10)]"
                  >
                    <Icon size={24} weight="fill" />
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>

      <div className="mx-auto w-full max-w-[72rem] px-6 pb-[54px] pt-[46px] md:pb-10 md:pt-0 lg:px-10">
        <p className={`text-[12px] leading-none ${INK_60} md:leading-normal`}>
          © {new Date().getFullYear()} bluntly.ph. All Rights Reserved.
        </p>
      </div>
    </footer>
  );
}

function FooterColumn({
  title,
  links,
}: {
  title: string;
  links: { label: string; href: string }[];
}) {
  return (
    <nav aria-label={title} className="mt-[31px] md:mt-0">
      {/* h2, not h3. The footer is on every page, and on pages whose main
          content is a card grid there is no h2 between the page h1 and these,
          so h3 skipped a level site-wide. */}
      <h2 className={`text-[12px] font-bold leading-[18px] ${INK_60} md:text-[13px] md:font-semibold md:text-[var(--text-primary)]`}>
        {title}
      </h2>
      {/* A 26px pitch of 12px lines. -my-1.5 py-1.5 makes each target 24px
          tall — the WCAG 2.5.8 floor — without changing the drawn rhythm. */}
      <ul className="mt-4 flex flex-col gap-[14px] md:mt-3 md:gap-1">
        {links.map((l) => (
          <li key={l.label}>
            <Link
              href={l.href}
              className={`-my-1.5 flex w-fit py-1.5 text-[12px] font-light leading-none ${INK_60} hover:text-[var(--text-primary)] md:my-0 md:min-h-[32px] md:items-center md:py-0 md:text-[13px] md:font-normal md:text-[var(--text-secondary)]`}
            >
              {l.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export default SiteFooter;
