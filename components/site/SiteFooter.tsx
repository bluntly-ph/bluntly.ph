import Link from "next/link";
import {
  FacebookLogo,
  InstagramLogo,
  RedditLogo,
  TiktokLogo,
} from "@phosphor-icons/react/dist/ssr";

import { Logo } from "@/components/ui/Logo";
import { FOOTER_LINKS } from "@/lib/landing-data";

// bluntly's own profiles. These were network homepages until BUG-002 — a
// "Follow us" icon that drops you on reddit.com follows nobody.
const SOCIALS = [
  { label: "Reddit", href: "https://www.reddit.com/r/bluntlyph", Icon: RedditLogo },
  { label: "Instagram", href: "https://www.instagram.com/bluntlyph", Icon: InstagramLogo },
  { label: "Facebook", href: "https://www.facebook.com/bluntlyph", Icon: FacebookLogo },
  { label: "TikTok", href: "https://www.tiktok.com/@bluntlyph", Icon: TiktokLogo },
];

/**
 * The site footer — brand, link columns, socials, copyright.
 *
 * Ground is --base-gray-200 (#d9d9d9), the footer colour in the Page 1 frame.
 * It sat on gray-150 (#eaeaea): close enough to look deliberate, wrong enough
 * that the footer never separated from the section above it.
 */
export function SiteFooter() {
  return (
    <footer className="mt-4 bg-[var(--base-gray-200)]">
      <div className="mx-auto grid w-full max-w-[72rem] gap-10 px-6 py-12 sm:grid-cols-2 lg:grid-cols-4 lg:px-10">
        <div className="sm:col-span-2 lg:col-span-1">
          <span className="text-[var(--accent-primary)]">
            <Logo height={24} label="bluntly" />
          </span>
        </div>

        <FooterColumn title="About" links={FOOTER_LINKS.about} />
        <FooterColumn title="Read" links={FOOTER_LINKS.read} />

        <div>
          <h3 className="text-[13px] font-semibold text-[var(--text-primary)]">
            Follow us
          </h3>
          <ul className="mt-4 flex gap-3">
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
      </div>

      <div className="mx-auto w-full max-w-[72rem] px-6 pb-10 lg:px-10">
        <p className="text-[12px] text-[var(--text-muted)]">
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
    <nav aria-label={title}>
      {/* h2, not h3. The footer is on every page, and on pages whose main
          content is a card grid there is no h2 between the page h1 and these,
          so h3 skipped a level site-wide. */}
      <h2 className="text-[13px] font-semibold text-[var(--text-primary)]">
        {title}
      </h2>
      {/* gap-3 was measured between 19px-tall links; the padding grows each
          target past the WCAG 2.5.8 floor and the reduced gap keeps the column
          the same height it was. */}
      <ul className="mt-3 flex flex-col gap-1">
        {links.map((l) => (
          <li key={l.label}>
            <Link
              href={l.href}
              className="inline-flex min-h-[32px] items-center text-[13px] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
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
