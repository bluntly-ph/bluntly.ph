"use client";

import { useId } from "react";
import type { InputHTMLAttributes, ReactNode } from "react";

/**
 * Labelled text input — 48px tall, 12px radius, matching the auth frames.
 *
 * The design draws the label as placeholder-style text inside the field. A real
 * placeholder disappears on focus and is not an accessible name, so the label is
 * a genuine <label> and stays visible; `error` wires to aria-describedby and
 * aria-invalid so the field errors from a 422 are announced, not just coloured.
 */

export type TextFieldProps = Omit<
  InputHTMLAttributes<HTMLInputElement>,
  "id" | "className"
> & {
  label: string;
  error?: string;
  hint?: string;
  adornment?: ReactNode;
};

export function TextField({
  label,
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
        className="text-[length:var(--text-xs)] text-[var(--text-secondary)]"
      >
        {label}
        {required ? (
          <span className="text-[var(--accent-danger)]" aria-hidden="true">
            {" *"}
          </span>
        ) : null}
      </label>

      <div className="relative flex items-center">
        {adornment ? (
          <span
            className="absolute left-4 text-[var(--text-muted)]"
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
            "bg-[var(--surface-card)] text-[length:var(--text-md)]",
            "text-[var(--text-primary)]",
            "placeholder:text-[var(--text-muted)]",
            "px-4 outline-none transition-shadow",
            "duration-[var(--duration-fast)] ease-[var(--ease-standard)]",
            adornment ? "pl-11" : "",
            error
              ? "shadow-[inset_0_0_0_1px_var(--accent-danger)]"
              : "shadow-[inset_0_0_0_1px_var(--line-hairline-30)] focus:shadow-[inset_0_0_0_2px_var(--accent-primary)]",
          ].join(" ")}
          {...rest}
        />
      </div>

      {hint && !error ? (
        <p id={hintId} className="text-[length:var(--text-2xs)] text-[var(--text-muted)]">
          {hint}
        </p>
      ) : null}

      {error ? (
        <p
          id={errorId}
          role="alert"
          className="text-[length:var(--text-2xs)] text-[var(--accent-danger)]"
        >
          {error}
        </p>
      ) : null}
    </div>
  );
}

export default TextField;
