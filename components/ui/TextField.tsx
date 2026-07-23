"use client";

import { useId } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";

/**
 * Text input — 48px tall, 12px radius, white fill with a 30%-ink hairline,
 * matching the "Let's get started!" and onboarding frames.
 *
 * The design shows only placeholder text inside the field. A placeholder is not
 * an accessible name and vanishes on focus, so a real <label> is always
 * rendered; where the frame shows no visible label the caller passes
 * `labelHidden` and it stays available to assistive tech only.
 */

export type TextFieldProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "id" | "className"
> & {
  label: string;
  labelHidden?: boolean;
  error?: string;
  hint?: string;
  adornment?: ReactNode;
};

export function TextField({
  label,
  labelHidden = false,
  error,
  hint,
  adornment,
  required,
  ...rest
}: TextFieldProps) {
  const id = useId();
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;
  const describedBy =
    [error ? errorId : null, hint ? hintId : null].filter(Boolean).join(" ") ||
    undefined;

  return (
    <div className="flex flex-col gap-2">
      <label
        htmlFor={id}
        className={
          labelHidden
            ? "sr-only"
            : "text-[14px] font-medium text-[var(--text-primary)]"
        }
      >
        {label}
      </label>

      <div className="relative flex items-center">
        {adornment ? (
          <span
            className="pointer-events-none absolute left-4 text-[14px] text-[var(--text-muted)]"
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
            "h-[var(--control-input-h)] w-full rounded-[var(--radius-sm)]",
            "bg-white text-[14px] text-[var(--text-primary)]",
            "placeholder:text-[var(--text-muted)]",
            "px-4 outline-none transition-shadow",
            "duration-[var(--duration-fast)] ease-[var(--ease-standard)]",
            adornment ? "pl-10" : "",
            error
              ? "shadow-[inset_0_0_0_1px_var(--accent-danger)]"
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
