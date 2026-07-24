"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { MagnifyingGlass, Plus, X } from "@phosphor-icons/react/dist/ssr";

import { Button } from "@/components/ui/Button";

type Product = { id: string; canonical_name: string | null };

export function AskQuestionForm() {
  const router = useRouter();
  const [product, setProduct] = useState<Product | null>(null);
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Product[]>([]);
  const [busy, setBusy] = useState(false);
  const [creating, setCreating] = useState(false);
  const [body, setBody] = useState("");
  const [directedTo, setDirectedTo] = useState<"buyers" | "seller">("buyers");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (product) return;
    const query = q.trim();
    if (query.length < 2) {
      setResults([]);
      return;
    }
    const t = setTimeout(async () => {
      try {
        const res = await fetch(
          `/api/bff/api/v1/products?q=${encodeURIComponent(query)}&limit=8`,
        );
        setResults(res.ok ? await res.json() : []);
      } catch {
        setResults([]);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [q, product]);

  async function createProduct() {
    if (!q.trim() || creating) return;
    setCreating(true);
    try {
      const res = await fetch("/api/bff/api/v1/products", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ name: q.trim() }),
      });
      if (res.ok) setProduct(await res.json());
    } finally {
      setCreating(false);
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!product || !body.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/bff/api/v1/questions", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          product_id: product.id,
          body: body.trim(),
          directed_to: directedTo,
        }),
      });
      if (!res.ok) {
        const p = (await res.json().catch(() => ({}))) as { detail?: string };
        setError(p.detail ?? "Couldn't post your question.");
        return;
      }
      const created = (await res.json()) as { id: string };
      router.push(`/questions/${created.id}`);
    } catch {
      setError("Couldn't reach the server.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit}>
      <h1 className="text-[24px] font-bold text-[var(--text-primary)]">Ask a question</h1>
      <p className="mt-1 text-[14px] text-[var(--text-secondary)]">
        Questions are about a specific product. Find it, then ask away.
      </p>

      <div className="mt-6 flex flex-col gap-5">
        {/* Product */}
        {product ? (
          <div className="flex items-center gap-3 rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-3 shadow-[var(--shadow-hairline-inset)]">
            <span className="h-9 w-9 shrink-0 rounded-[8px] bg-[var(--base-gray-200)]" />
            <span className="flex-1 text-[14px] font-medium text-[var(--text-primary)]">
              {product.canonical_name ?? "Selected product"}
            </span>
            <button
              type="button"
              onClick={() => setProduct(null)}
              className="grid h-7 w-7 place-items-center rounded-full text-[var(--text-muted)] hover:bg-[var(--line-hairline-10)]"
              aria-label="Change product"
            >
              <X size={16} />
            </button>
          </div>
        ) : (
          <div>
            <div className="relative">
              <MagnifyingGlass
                size={20}
                className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
              />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Which product?"
                className="h-12 w-full rounded-[var(--radius-pill)] bg-[var(--surface-card)] pl-11 pr-4 text-[14px] text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)] outline-none placeholder:text-[var(--text-muted)] focus-visible:shadow-[0_0_0_2px_var(--accent-primary)]"
              />
            </div>
            <ul className="mt-3 flex flex-col gap-2">
              {results.map((p) => (
                <li key={p.id}>
                  <button
                    type="button"
                    onClick={() => setProduct(p)}
                    className="flex w-full items-center gap-3 rounded-[var(--radius-sm)] bg-[var(--surface-card)] p-3 text-left shadow-[var(--shadow-hairline-inset)] hover:outline hover:outline-1 hover:outline-[var(--accent-primary)]"
                  >
                    <span className="h-8 w-8 shrink-0 rounded-[8px] bg-[var(--base-gray-200)]" />
                    <span className="text-[14px] text-[var(--text-primary)]">
                      {p.canonical_name ?? "Unnamed product"}
                    </span>
                  </button>
                </li>
              ))}
              {q.trim().length >= 2 ? (
                <li>
                  <button
                    type="button"
                    onClick={createProduct}
                    disabled={creating}
                    className="flex w-full items-center gap-3 rounded-[var(--radius-sm)] border border-dashed border-[var(--line-hairline-30)] p-3 text-left hover:border-[var(--accent-primary)] disabled:opacity-60"
                  >
                    <span className="grid h-8 w-8 shrink-0 place-items-center rounded-[8px] bg-[color-mix(in_srgb,var(--accent-primary)_12%,transparent)] text-[var(--accent-primary)]">
                      <Plus size={16} weight="bold" />
                    </span>
                    <span className="text-[14px] text-[var(--text-primary)]">
                      Add &ldquo;{q.trim()}&rdquo;
                    </span>
                  </button>
                </li>
              ) : null}
            </ul>
          </div>
        )}

        {/* Question */}
        <label className="flex flex-col gap-1.5">
          <span className="text-[13px] font-medium text-[var(--text-primary)]">Your question</span>
          <textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={4}
            placeholder="What do you want to know before buying?"
            className="w-full resize-y rounded-[var(--radius-sm)] bg-[var(--surface-card)] px-4 py-3 text-[14px] text-[var(--text-primary)] shadow-[var(--shadow-hairline-inset)] outline-none placeholder:text-[var(--text-muted)] focus-visible:shadow-[0_0_0_2px_var(--accent-primary)]"
          />
        </label>

        {/* Directed to */}
        <div className="flex items-center gap-3">
          <span className="text-[13px] font-medium text-[var(--text-primary)]">Ask</span>
          <div className="flex gap-2">
            {(["buyers", "seller"] as const).map((v) => (
              <button
                key={v}
                type="button"
                onClick={() => setDirectedTo(v)}
                className={`rounded-[var(--radius-pill)] px-4 py-1.5 text-[13px] font-medium ${
                  directedTo === v
                    ? "bg-[var(--accent-primary)] text-white"
                    : "bg-[var(--surface-card)] text-[var(--text-secondary)] shadow-[var(--shadow-hairline-inset)]"
                }`}
              >
                {v === "buyers" ? "Other buyers" : "The seller"}
              </button>
            ))}
          </div>
        </div>

        {error ? (
          <p role="alert" className="rounded-[var(--radius-sm)] bg-[color-mix(in_srgb,var(--accent-danger)_10%,transparent)] px-4 py-3 text-[13px] text-[var(--accent-danger)]">
            {error}
          </p>
        ) : null}

        <div>
          <Button type="submit" disabled={!product || !body.trim() || busy}>
            {busy ? "Posting…" : "Post question"}
          </Button>
        </div>
      </div>
    </form>
  );
}

export default AskQuestionForm;
