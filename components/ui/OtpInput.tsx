"use client";

import { useRef, useState } from "react";
import type { ChangeEvent, ClipboardEvent, KeyboardEvent } from "react";

/**
 * Six-digit code entry.
 *
 * Renders six boxes for the look the design asks for, but keeps a single hidden
 * input as the form value so the whole thing submits as one `code` field and
 * password managers / SMS autofill see one target.
 *
 * `inputMode="numeric"` and `autoComplete="one-time-code"` matter here: they are
 * what make a phone show a number pad and offer the code from the notification.
 */

const LENGTH = 6;

export type OtpInputProps = {
  name?: string;
  error?: string;
  autoFocus?: boolean;
  onComplete?: (code: string) => void;
};

export function OtpInput({
  name = "code",
  error,
  autoFocus = true,
  onComplete,
}: OtpInputProps) {
  const [digits, setDigits] = useState<string[]>(Array(LENGTH).fill(""));
  const refs = useRef<(HTMLInputElement | null)[]>([]);
  const value = digits.join("");

  function commit(next: string[]) {
    setDigits(next);
    const joined = next.join("");
    if (joined.length === LENGTH && !joined.includes("")) onComplete?.(joined);
  }

  function handleChange(index: number, event: ChangeEvent<HTMLInputElement>) {
    const typed = event.target.value.replace(/\D/g, "");
    if (!typed) return;
    const next = [...digits];
    // Typing over a filled box replaces it; pasting many digits fills forward.
    for (let i = 0; i < typed.length && index + i < LENGTH; i += 1) {
      next[index + i] = typed[i];
    }
    commit(next);
    const focusAt = Math.min(index + typed.length, LENGTH - 1);
    refs.current[focusAt]?.focus();
  }

  function handleKeyDown(index: number, event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Backspace") {
      event.preventDefault();
      const next = [...digits];
      if (next[index]) {
        next[index] = "";
        commit(next);
      } else if (index > 0) {
        next[index - 1] = "";
        commit(next);
        refs.current[index - 1]?.focus();
      }
    }
    if (event.key === "ArrowLeft" && index > 0) refs.current[index - 1]?.focus();
    if (event.key === "ArrowRight" && index < LENGTH - 1) {
      refs.current[index + 1]?.focus();
    }
  }

  function handlePaste(event: ClipboardEvent<HTMLInputElement>) {
    const pasted = event.clipboardData.getData("text").replace(/\D/g, "");
    if (!pasted) return;
    event.preventDefault();
    const next = Array(LENGTH)
      .fill("")
      .map((_, i) => pasted[i] ?? "");
    commit(next);
    refs.current[Math.min(pasted.length, LENGTH - 1)]?.focus();
  }

  return (
    <div className="flex flex-col gap-2">
      <input type="hidden" name={name} value={value} />
      <div
        className="flex justify-between gap-2"
        role="group"
        aria-label="Six digit verification code"
      >
        {digits.map((digit, index) => (
          <input
            // Fixed-length positional boxes; index is the stable identity here.
            key={index}
            ref={(el) => {
              refs.current[index] = el;
            }}
            value={digit}
            onChange={(e) => handleChange(index, e)}
            onKeyDown={(e) => handleKeyDown(index, e)}
            onPaste={handlePaste}
            autoFocus={autoFocus && index === 0}
            inputMode="numeric"
            autoComplete={index === 0 ? "one-time-code" : "off"}
            maxLength={LENGTH}
            aria-label={`Digit ${index + 1}`}
            aria-invalid={error ? true : undefined}
            className={[
              "h-14 w-full min-w-0 rounded-[var(--radius-sm)] text-center",
              "bg-[var(--surface-card)] text-[length:var(--text-xl)]",
              "text-[var(--text-primary)] outline-none",
              "transition-shadow duration-[var(--duration-fast)]",
              error
                ? "shadow-[inset_0_0_0_1px_var(--accent-danger)]"
                : "shadow-[inset_0_0_0_1px_var(--line-hairline-30)] focus:shadow-[inset_0_0_0_2px_var(--accent-primary)]",
            ].join(" ")}
          />
        ))}
      </div>
      {error ? (
        <p role="alert" className="text-[length:var(--text-2xs)] text-[var(--accent-danger)]">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export default OtpInput;
