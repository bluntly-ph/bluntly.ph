import Link from "next/link";
import {
  FacebookLogo,
  InstagramLogo,
  RedditLogo,
  TiktokLogo,
} from "@phosphor-icons/react/dist/ssr";

import { Logo } from "@/components/ui/Logo";
import { FOOTER_LINKS } from "@/lib/landing-data";

const SOCIALS = [
  { label: "Reddit", href: "https://reddit.com", Icon: RedditLogo },
  { label: "Instagram", href: "https://instagram.com", Icon: InstagramLogo },
  { label: "Facebook", href: "https://facebook.com", Icon: FacebookLogo },
  { label: "TikTok", href: "https://tiktok.com", Icon: TiktokLogo },
];

/** The site footer — brand, link columns, socials, copyright. */
export function SiteFooter() {
  return (
    <footer className="mt-4 bg-[var(--base-gray-150)]">
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
      <h3 className="text-[13px] font-semibold text-[var(--text-primary)]">
        {title}
      </h3>
      <ul className="mt-4 flex flex-col gap-3">
        {links.map((l) => (
          <li key={l.label}>
            <Link
              href={l.href}
              className="text-[13px] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
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
