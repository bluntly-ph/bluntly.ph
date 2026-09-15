"use client";

import { useId } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";

/**
 * Text input — Figma "TextField" (6808:456): 48px tall, 12px radius, white fill
 * with a 30%-ink hairline, 16px in.
 *
 * Two treatments the frames draw beyond it:
 *   fieldSize "lg"   the gradient auth screens' field (5348:2789): 52px, 16px
 *                    Regular at 0.8px tracking, placeholder at 40%
 *   tone "soft"      the onboarding UsernameField (5369:3079): white at 30%
 *                    with no hairline, a 20px glyph 8px before the value
 *
 * The design shows only placeholder text inside the field. A placeholder is not
 * an accessible name and vanishes on focus, so a real <label> is always
 * rendered; where the frame shows no visible label the caller passes
 * `labelHidden` and it stays available to assistive tech only.
 */

export type TextFieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, "id" | "className" | "size"> & {
  label: string;
  labelHidden?: boolean;
  error?: string;
  hint?: string;
  adornment?: ReactNode;
  fieldSize?: "md" | "lg";
  tone?: "outline" | "soft";
};

export function TextField({
  label,
  labelHidden = false,
  error,
  hint,
  adornment,
  fieldSize = "md",
  tone = "outline",
  required,
  ...rest
}: TextFieldProps) {
  const id = useId();
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;
  const describedBy = [error ? errorId : null, hint ? hintId : null].filter(Boolean).join(" ") || undefined;
  const large = fieldSize === "lg";
  const soft = tone === "soft";

  return (
    <div className="flex flex-col gap-2">
      <label
        htmlFor={id}
        className={labelHidden ? "sr-only" : "text-[14px] font-medium leading-none text-[var(--text-primary)]"}
      >
        {label}
      </label>

      <div className="relative flex items-center">
        {adornment ? (
          <span
            className="pointer-events-none absolute left-4 flex items-center text-[14px] text-[var(--text-muted)]"
            aria-hidden="true"
          >
            {adornment}
          </span>
        ) : null}
        <input
          id={id}
          required={required}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={[
            large ? "h-[52px]" : "h-[var(--control-input-h)]",
            "w-full rounded-[var(--radius-sm)]",
            // White reads as a field against the mobile sheet's gray-100; on the
            // desktop card that inverts, so the field takes the gray instead.
            soft ? "bg-[rgba(255,255,255,0.3)]" : "bg-white",
            "lg:bg-[var(--surface-input)]",
            large
              ? "text-[16px] tracking-[0.8px] placeholder:text-[rgba(32,32,32,0.4)]"
              : "text-[14px] placeholder:text-[var(--text-muted)]",
            "text-[var(--text-primary)]",
            "px-4 outline-none transition-shadow",
            "duration-[var(--duration-fast)] ease-[var(--ease-standard)]",
            adornment ? (large ? "pl-11" : "pl-10") : "",
            error
              ? "shadow-[inset_0_0_0_1px_var(--accent-danger)]"
              : soft
                ? "focus:shadow-[inset_0_0_0_1px_var(--accent-primary)]"
                : "shadow-[inset_0_0_0_1px_var(--line-hairline-30)] focus:shadow-[inset_0_0_0_2px_var(--accent-primary)]",
          ].join(" ")}
          {...rest}
        />
      </div>

      {hint && !error ? (
        <p id={hintId} className="text-[12px] text-[var(--text-muted)]">
          {hint}
        </p>
      ) : null}

      {error ? (
        <p id={errorId} role="alert" className="text-[12px] text-[var(--accent-danger)]">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export default TextField;
