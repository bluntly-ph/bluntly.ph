import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";

/**
 * A call to action that navigates — an anchor styled as the design's pill
 * button. Use this instead of wrapping `<Button>` in a `<Link>`.
 *
 * It exists because of two QA findings that turned out to be the same mistake
 * made in two directions:
 *
 * QA-007 — the informational pages hand-rolled their CTAs as `<Link>` elements
 * carrying `text-white`, and placed them inside `<Article className="prose">`.
 * `.prose a { color: var(--accent-primary) }` is specificity (0,0,1,1) and
 * Tailwind's `.text-white` is (0,0,1,0), so the prose rule won: orange label on
 * an orange fill, invisible until hover tinted the background. Every CTA here
 * carries `data-cta`, and the prose rule now excludes it — so the fix holds
 * wherever a CTA lands inside prose, not just on the four pages QA happened to
 * open.
 *
 * QA-012 — "Post a request" and "Ask a question" were `<Link className="contents">`
 * wrapped around `<Button>`. That nests a button inside an anchor, which is
 * invalid, and a `<button>` renders with `cursor: default`, so neither read as
 * clickable. An anchor is the correct element for something that navigates, and
 * it gets the pointer cursor for free.
 */

type Variant = "primary" | "secondary";
type Size = "sm" | "md";

/**
 * Sizes are a prop, not a className override. Without tailwind-merge in this
 * project a caller passing `h-9 px-4` loses to the base `h-11 px-6` on
 * stylesheet order alone — the override is silently dropped, which is how the
 * page-title CTAs grew from a 31px chip to a 44px pill while "fixing" QA-012.
 */
const SIZES: Record<Size, string> = {
  sm: "h-9 px-4 text-[13px]",
  md: "h-11 px-6 text-[14px]",
};

const VARIANTS: Record<Variant, string> = {
  // `!text-white` is deliberate belt-and-braces: the prose exclusion below
  // already wins, but a CTA that silently loses its label is exactly the bug
  // this component was created for, and the important-flag costs nothing.
  primary:
    "bg-[var(--accent-primary)] !text-white shadow-[var(--shadow-card)] " +
    "hover:bg-[var(--accent-primary-strong)]",
  secondary:
    "bg-[var(--surface-card)] !text-[var(--text-primary)] " +
    "shadow-[var(--shadow-hairline-inset)] hover:!text-[var(--accent-primary)]",
};

export type CtaLinkProps = ComponentProps<typeof Link> & {
  variant?: Variant;
  size?: Size;
  icon?: ReactNode;
  fullWidth?: boolean;
};

export function CtaLink({
  children,
  variant = "primary",
  size = "md",
  icon = null,
  fullWidth = false,
  className = "",
  ...rest
}: CtaLinkProps) {
  return (
    <Link
      // Read by `.prose a:not([data-cta])` in globals.css. Without it a CTA
      // inside an article inherits the prose link colour and underline.
      data-cta=""
      className={[
        "inline-flex cursor-pointer items-center justify-center gap-2",
        "rounded-[var(--radius-pill)] font-semibold no-underline",
        SIZES[size],
        "transition-colors duration-[var(--duration-fast)] ease-[var(--ease-standard)]",
        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2",
        "focus-visible:outline-[var(--accent-primary)]",
        "active:scale-[0.97] motion-reduce:active:scale-100",
        VARIANTS[variant],
        fullWidth ? "w-full" : "",
        className,
      ].join(" ")}
      {...rest}
    >
      {icon}
      {children}
    </Link>
  );
}

export default CtaLink;
