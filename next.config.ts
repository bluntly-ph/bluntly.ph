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
 */
const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
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
