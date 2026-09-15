"use client";

import { useEffect, useState } from "react";

/**
 * Compact counts, the way the design writes them: "12.9k", "₱2.4k".
 */
export function compactNumber(n: number): string {
  if (n < 1000) return String(Math.round(n));
  if (n < 1_000_000) return `${(n / 1000).toFixed(1).replace(/\.0$/, "")}k`;
  return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, "")}m`;
}

type Stats = { reviews: number; helped: number; commission: number };

/**
 * "Your latest stats:" on the All done screens, Figma "Reviewer Page - All
 * done" (4550:8882) and "Seller Review - All done" (4652:12914): the label in
 * 12px Regular trust blue, 26px over three figures in 28px Medium brand orange
 * with 12px Light labels at 70%, 20px apart and centred.
 *
 * INTENTIONAL PRODUCT DIFFERENCE: the frames print sample figures. These are
 * the reviewer's own dashboard numbers over the last 90 days
 * (GET /users/me/dashboard), and the block is left out when they cannot be read.
 */
export function LatestStats({ className = "" }: { className?: string }) {
  const [stats, setStats] = useState<Stats | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/bff/api/v1/users/me/dashboard?range=90d")
      .then((res) => (res.ok ? res.json() : null))
      .then((summary: { reviews?: { helped?: number }[]; estimated_commission?: string } | null) => {
        if (cancelled || !summary || !Array.isArray(summary.reviews)) return;
        setStats({
          reviews: summary.reviews.length,
          helped: summary.reviews.reduce((n, r) => n + (r.helped ?? 0), 0),
          commission: Number(summary.estimated_commission ?? 0) || 0,
        });
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  if (!stats) return null;

  const figures = [
    { value: compactNumber(stats.reviews), label: "Reviews Posted" },
    { value: compactNumber(stats.helped), label: "People Helped" },
    { value: `₱${compactNumber(stats.commission)}`, label: "Commission Earned" },
  ];

  return (
    <div className={className}>
      <p className="text-[12px] leading-none text-[var(--accent-trust)]">Your latest stats:</p>
      <dl className="mt-[26px] flex justify-center gap-5">
        {figures.map((f) => (
          <div key={f.label} className="flex flex-col-reverse items-center">
            <dt className="text-[12px] font-light leading-none text-[rgba(32,32,32,0.7)]">{f.label}</dt>
            <dd className="text-[28px] font-medium leading-[42px] text-[var(--accent-primary)]">{f.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export default LatestStats;
