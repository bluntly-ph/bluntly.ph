import type { NextConfig } from "next";

/**
 * Security headers.
 *
 * The app holds a session in an httpOnly cookie and proxies an authenticated
 * API, so the headers below are load-bearing rather than decoration:
 * clickjacking a signed-in page or sniffing a response type both lead
 * somewhere real.
 *
 * CSP omits `unsafe-eval` but must keep `unsafe-inline` for styles: Next
 * injects inline <style> for the CSS it extracts, and next/font emits inline
 * @font-face. Locking scripts down further needs per-request nonces, which
 * means moving CSP into proxy.ts — worth doing, but it is a change with its own
 * failure modes and belongs on its own.
 *
 * `unsafe-eval` is added in DEVELOPMENT ONLY. Turbopack's dev server ships its
 * module runtime through `eval`, so without it Firefox and WebKit fill the
 * console with CSP violations and the console-health E2E suite fails on every
 * page — a false alarm that hides real errors. The production build emits no
 * `eval`, so the shipped policy is unchanged and stays the strict one.
 */
const isDev = process.env.NODE_ENV === "development";

const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https://*.supabase.co",
  "font-src 'self' data:",
  // The browser only ever talks to this origin; the API is reached server-side.
  "connect-src 'self'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join("; ");

const nextConfig: NextConfig = {
  // Do not advertise the framework and its version.
  poweredByHeader: false,

  /**
   * Product and review photographs are served from Supabase Storage, and this
   * project's storage will not emit a cacheable `Cache-Control` for them.
   *
   * Measured on production 2026-08-23: every public object answers
   * `Cache-Control: no-cache`, and it is not a matter of how they were
   * uploaded. The objects' stored metadata was corrected to
   * `max-age=31536000` (see backend/scripts/backfill_image_cache_headers.py)
   * and a freshly uploaded probe carried the header too — both still served
   * `no-cache`, cache-busted, straight from origin. So the bytes are refetched
   * in full on every page load, and the 120 KB product image is `/search`'s
   * LCP element at 9.25 s under Lighthouse throttling. `/feed` only scores
   * better because its LCP happens to be a text node.
   *
   * Routing them through the built-in optimizer puts the caching decision back
   * on our side of the wire, and resizes at the same time — the heaviest
   * product image in production is an 887 KB PNG drawn into a 96 px box.
   */
  images: {
    // NOT the built-in optimizer: `/_next/image` 404s in this deployment,
    // because vercel.json rewrites every path to a service and a function
    // route does not survive that. See lib/supabase-image-loader.ts — the
    // resizing and the year-long cache header both come from Supabase's own
    // render endpoint instead. `remotePatterns` is deliberately absent: it
    // governs the built-in optimizer, which is not in play here.
    loader: "custom",
    loaderFile: "./lib/supabase-image-loader.ts",
  },

  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
          },
          {
            // Only meaningful over HTTPS; browsers ignore it on plain http,
            // so it is safe to send in development too.
            key: "Strict-Transport-Security",
            value: "max-age=63072000; includeSubDomains; preload",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
