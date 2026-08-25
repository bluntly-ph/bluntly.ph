import Link from "next/link";
import {
  Bell,
  Cube,
  Fingerprint,
  Gear,
  Handbag,
  Link as LinkIcon,
  ListChecks,
  PiggyBank,
  Question,
  Storefront,
  Warning,
  UsersThree,
} from "@phosphor-icons/react/dist/ssr";

/**
 * The admin console shell, built to the approved Admin Page frame
 * (5017:1738, 1280x832).
 *
 * The frame is a desktop console: a 220px white sidebar with four labelled
 * groups and a user card pinned to its foot, beside a light working area. That
 * is a different information architecture from the single scrolling page
 * /moderate used to be, which is why the owner kept saying it did not look
 * 1:1 — the gap was structural, not cosmetic.
 *
 * DOCUMENTED DEVIATION — unbuilt destinations
 *   FIGMA:          ten navigation items, all rendered identically.
 *   IMPLEMENTATION: the items with a real destination link; the rest are
 *                   present, in position, visibly marked "Soon" and not
 *                   focusable.
 *   WHY:            Products, Sellers, Reviewers, Affiliate Links, Honesty
 *                   Fund, Activity Log and Settings have no page behind them
 *                   yet. Rendering them as live links would put seven dead
 *                   controls in the primary navigation of an admin tool.
 *                   Their position and labels are kept so the structure still
 *                   matches the frame.
 *   EVIDENCE:       brief — "Do not implement a dead fullscreen icon... If
 *                   fullscreen is not useful in Bluntly, omit it rather than
 *                   leaving fake controls." Same principle, applied to nav.
 */

type NavItem = {
  label: string;
  Icon: typeof Cube;
  href?: string;
};

const GROUPS: { heading: string; items: NavItem[] }[] = [
  {
    heading: "Main",
    items: [
      { label: "Overview", Icon: Cube, href: "/moderate" },
      { label: "Review Queue", Icon: ListChecks, href: "/moderate#queue" },
      { label: "Q&A", Icon: Question, href: "/questions" },
    ],
  },
  {
    heading: "Manage",
    items: [
      { label: "Products", Icon: Handbag },
      { label: "Sellers", Icon: Storefront },
      { label: "Reviewers", Icon: UsersThree },
    ],
  },
  {
    heading: "Finance",
    items: [
      { label: "Affiliate Links", Icon: LinkIcon },
      { label: "Honesty Fund", Icon: PiggyBank },
    ],
  },
  {
    heading: "System",
    items: [
      { label: "Activity Log", Icon: Fingerprint },
      { label: "Settings", Icon: Gear },
    ],
  },
];

export function AdminShell({
  active,
  moderator,
  urgent,
  title,
  children,
}: {
  active: string;
  moderator: { name: string; role: string };
  urgent: number;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-dvh bg-[var(--surface-app)]">
      {/* The frame's sidebar is a desktop device. Below `lg` it would take
          most of a phone's width, so the console falls back to the working
          area alone and navigation lives in the page. */}
      <aside className="hidden w-[220px] shrink-0 flex-col border-r border-[var(--border-subtle)] bg-[var(--surface-card)] lg:flex">
        <div className="px-6 pb-6 pt-5">
          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[var(--accent-trust)]">
            Admin
          </p>
          <p className="font-[family-name:var(--font-display)] text-[22px] font-bold leading-none text-[var(--accent-primary)]">
            bluntly
          </p>
        </div>

        <nav aria-label="Admin sections" className="flex-1 px-3">
          {GROUPS.map((group) => (
            <div key={group.heading} className="mb-5">
              <p className="px-3 pb-2 text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--text-muted)]">
                {group.heading}
              </p>
              <ul className="flex flex-col gap-0.5">
                {group.items.map(({ label, Icon, href }) => {
                  const isActive = label === active;
                  const className =
                    "flex items-center gap-2.5 whitespace-nowrap rounded-[var(--radius-sm)] px-3 py-2 text-[14px] font-medium";
                  return (
                    <li key={label}>
                      {href ? (
                        <Link
                          href={href}
                          aria-current={isActive ? "page" : undefined}
                          className={`${className} transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)] ${
                            isActive
                              ? "bg-[var(--line-hairline-10)] text-[var(--accent-primary)]"
                              : "text-[var(--text-primary)] hover:bg-[var(--line-hairline-10)]"
                          }`}
                        >
                          <Icon size={20} weight={isActive ? "fill" : "regular"} />
                          {label}
                        </Link>
                      ) : (
                        <span
                          className={`${className} cursor-default text-[var(--text-muted)]`}
                        >
                          <Icon size={20} weight="regular" />
                          {label}
                          <span className="ml-auto shrink-0 rounded-[var(--radius-pill)] bg-[var(--surface-app)] px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide">
                            Soon
                          </span>
                        </span>
                      )}
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        <div className="m-3 flex items-center gap-3 rounded-[var(--radius-sm)] p-3 shadow-[var(--shadow-hairline-inset)]">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-[var(--accent-primary)] text-[13px] font-bold text-[var(--text-on-brand)]">
            {moderator.name.slice(0, 1).toUpperCase()}
          </span>
          <span className="min-w-0">
            <span className="block truncate text-[13px] font-semibold text-[var(--text-primary)]">
              {moderator.name}
            </span>
            <span className="block text-[12px] capitalize text-[var(--text-secondary)]">
              {moderator.role}
            </span>
          </span>
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-3 px-4 py-5 sm:px-8">
          <h1 className="inline-flex items-center gap-2 rounded-[var(--radius-md)] bg-[var(--surface-card)] px-4 py-2.5 text-[18px] font-bold text-[var(--text-primary)] shadow-[var(--shadow-card)]">
            <Cube size={22} weight="regular" />
            {title}
          </h1>

          {urgent > 0 ? (
            <Link
              href="/moderate#queue"
              className="ml-auto inline-flex items-center gap-2 rounded-[var(--radius-md)] bg-[var(--surface-card)] px-4 py-2.5 shadow-[var(--shadow-card)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]"
            >
              <Warning
                size={18}
                weight="regular"
                className="text-[var(--accent-danger)]"
              />
              <span className="text-[14px] font-semibold text-[var(--accent-danger)]">
                {urgent} urgent
              </span>
              <Bell size={20} weight="fill" className="text-[var(--accent-primary)]" />
            </Link>
          ) : null}
        </div>

        <div className="px-4 pb-12 sm:px-8">{children}</div>
      </div>
    </div>
  );
}
