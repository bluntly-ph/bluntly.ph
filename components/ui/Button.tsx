import type { ButtonHTMLAttributes, ReactNode } from "react";

/**
 * Pill button — the source file's dominant CTA shape (32px full-pill radius).
 *
 * Re-implemented in Tailwind from the design system's Button, which styles via
 * inline React style objects. Inline styles cannot express :hover,
 * :focus-visible, or :active, and its press state used onMouseDown, which never
 * fires on touch. Every value below still comes from the DS tokens.
 */

type Variant = "primary" | "secondary" | "ghost" | "subtle";
type Size = "sm" | "md";

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-[var(--accent-primary)] text-[var(--text-on-brand)] shadow-[var(--shadow-card)] " +
    "hover:bg-[var(--accent-primary-strong)]",
  secondary:
    "bg-transparent text-[var(--text-primary)] shadow-[inset_0_0_0_1px_var(--base-ink-800)] " +
    "hover:bg-[var(--line-hairline-10)]",
  ghost:
    "bg-transparent text-[var(--accent-primary)] shadow-[inset_0_0_0_1px_var(--accent-primary)] " +
    "hover:bg-[color-mix(in_srgb,var(--accent-primary)_10%,transparent)]",
  subtle:
    "bg-[var(--base-gray-100)] text-[var(--text-primary)] hover:bg-[var(--base-gray-150)]",
};

const SIZES: Record<Size, string> = {
  sm: "text-[length:var(--text-xs)] px-4 py-[7px]",
  md: "text-[length:var(--text-md)] px-7 h-[var(--control-button-h)]",
};

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  icon?: ReactNode;
  fullWidth?: boolean;
};

export function Button({
  children,
  variant = "primary",
  size = "md",
  icon = null,
  fullWidth = false,
  className = "",
  disabled,
  ...rest
}: ButtonProps) {
  return (
    <button
      disabled={disabled}
      className={[
        "inline-flex items-center justify-center gap-2 rounded-[var(--radius-pill)]",
        "font-[family-name:var(--font-body)] font-normal leading-none",
        "transition-[opacity,transform,background-color]",
        "duration-[var(--duration-fast)] ease-[var(--ease-standard)]",
        // active: works for both pointer and touch, unlike onMouseDown.
        "active:scale-[0.97] motion-reduce:active:scale-100",
        "disabled:cursor-not-allowed disabled:opacity-40 disabled:active:scale-100",
        "disabled:hover:bg-[var(--base-gray-200)]",
        VARIANTS[variant],
        SIZES[size],
        fullWidth ? "w-full" : "",
        className,
      ].join(" ")}
      {...rest}
    >
      {icon}
      {children}
    </button>
  );
}

export default Button;
