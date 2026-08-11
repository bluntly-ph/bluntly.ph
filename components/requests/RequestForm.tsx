"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/Button";

/**
 * Post a review request. The bounty is escrowed from your token balance; the
 * backend AI-screens it (422 `request_invalid` returns `reasons[]`), and short
 * balances come back 409 `insufficient_tokens`.
 *
 * `tokenBalance` is read on the server (BUG-025). Before it was passed in, that
 * 409 was the *first* time anyone learned they couldn't afford the request —
 * after writing the whole thing — and there was nowhere on the page to check.
 * Null means the balance couldn't be read, which must not be conflated with
 * zero: we show nothing and let the server be the judge, rather than blocking
 * someone who can actually afford it.
 */
export function RequestForm({ tokenBalance }: { tokenBalance: number | null }) {
  const router = useRouter();
  const [title, setTitle] = useState("");
  const [details, setDetails] = useState("");
  const [bounty, setBounty] = useState(50);
  const [sourceUrl, setSourceUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);

  const affordable = tokenBalance === null || bounty <= tokenBalance;
  const ready = title.trim() && details.trim() && bounty > 0 && affordable;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!ready || busy) return;
    setBusy(true);
    setErrors([]);
    try {
      const res = await fetch("/api/bff/api/v1/requests", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          title: title.trim(),
          details: details.trim(),
          bounty,
          source_url: sourceUrl.trim() || null,
        }),
      });
      if (!res.ok) {
        const p = (await res.json().catch(() => ({}))) as {
          detail?: string;
          reasons?: string[];
        };
        setErrors(p.reasons?.length ? p.reasons : [p.detail ?? "Couldn't post that request."]);
        return;
      }
      router.push("/requests");
    } catch {
      setErrors(["Couldn't reach the server."]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <h1 className="text-[24px] font-bold text-[var(--text-primary)]">
        Ask for a review
      </h1>
      <p className="mt-1 text-[14px] text-[var(--text-secondary)]">
        Put up a token bounty — a reviewer who answers with a published review earns it.
      </p>

      {tokenBalance !== null ? (
        <p className="mt-4 inline-flex items-center gap-2 rounded-[var(--radius-pill)] bg-[var(--surface-card)] px-4 py-2 text-[13px] text-[var(--text-secondary)] shadow-[var(--shadow-hairline-inset)]">
          You have{" "}
          <span className="font-semibold text-[var(--text-primary)]">
            {tokenBalance.toLocaleString("en-PH")} tokens
          </span>
        </p>
      ) : null}

      <div className="mt-6 flex flex-col gap-5">
        <label className="flex flex-col gap-1.5">
          <span className="text-[13px] font-medium text-[var(--text-primary)]">What do you want reviewed?</span>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={200}
            placeholder="Is the Ugreen 145W power bank worth it?"
            className={inputCls}
          />
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="text-[13px] font-medium text-[var(--text-primary)]">Details</span>
          <textarea
            value={details}
            onChange={(e) => setDetails(e.target.value)}
            rows={4}
            placeholder="What specifically are you unsure about?"
            className={`${inputCls} resize-y py-3`}
          />
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="text-[13px] font-medium text-[var(--text-primary)]">Shopee / Lazada link (optional)</span>
          <input
            value={sourceUrl}
            onChange={(e) => setSourceUrl(e.target.value)}
            placeholder="https://shopee.ph/…"
            className={inputCls}
          />
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="text-[13px] font-medium text-[var(--text-primary)]">Bounty (tokens)</span>
          <input
            type="number"
            min={1}
            value={bounty}
            onChange={(e) => setBounty(Math.max(1, Number(e.target.value)))}
            className={`${inputCls} max-w-[10rem]`}
          />
          {!affordable && tokenBalance !== null ? (
            <span role="alert" className="text-[12px] text-[var(--accent-danger)]">
              That&rsquo;s more than your {tokenBalance.toLocaleString("en-PH")}{" "}
              tokens. Lower the bounty to {tokenBalance.toLocaleString("en-PH")} or
              less.
            </span>
          ) : null}
        </label>

        {errors.length > 0 ? (
          <ul role="alert" className="flex flex-col gap-1 rounded-[var(--radius-sm)] bg-[color-mix(in_srgb,var(--accent-danger)_10%,transparent)] px-4 py-3 text-[13px] text-[var(--accent-danger)]">
            {errors.map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        ) : null}

        <div className="flex items-center gap-3">
          <Button type="submit" disabled={!ready || busy}>
            {busy ? "Posting…" : `Post request (${bounty} tokens)`}
          </Button>
        </div>
      </div>
    </form>
  );
}

const inputCls =
  "w-full rounded-[var(--radius-sm)] bg-[var(--surface-card)] px-4 py-2.5 text-[14px] text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)] outline-none placeholder:text-[var(--text-muted)] focus-visible:shadow-[0_0_0_2px_var(--accent-primary)]";
