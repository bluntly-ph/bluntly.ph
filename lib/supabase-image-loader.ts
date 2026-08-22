"use client";

/**
 * Serve Supabase-hosted images through Supabase's own image transformation.
 *
 * The built-in optimizer is not reachable in this deployment. `vercel.json`
 * routes every path to a *service* (the app is deployed alongside the FastAPI
 * backend), and `/_next/image` is a function route rather than a static asset:
 * it does not survive the rewrite and lands on the app's own 404 page. Static
 * chunks under `/_next/static` are unaffected, which is why this was invisible
 * until an <Image> actually asked for one.
 *
 * Supabase's render endpoint does the same job on the storage side:
 *
 *   /storage/v1/object/public/<path>          120,455 B, Cache-Control: no-cache
 *   /storage/v1/render/image/public/<path>     22,412 B, Cache-Control: max-age=31536000
 *
 * Both measured on production 2026-08-23 for the same object at width 240. The
 * long max-age comes from the object metadata corrected by
 * backend/scripts/backfill_image_cache_headers.py — the render endpoint honours
 * that metadata even though the plain object endpoint does not. Format is
 * negotiated from the browser's Accept header, so real browsers get WebP.
 *
 * Anything that is not a Supabase public object is returned untouched, so a
 * blob: preview or a future host still renders rather than 404ing.
 */

const PUBLIC_OBJECT = "/storage/v1/object/public/";
const RENDER_IMAGE = "/storage/v1/render/image/public/";

export default function supabaseImageLoader({
  src,
  width,
  quality,
}: {
  src: string;
  width: number;
  quality?: number;
}): string {
  if (!src.includes(PUBLIC_OBJECT)) return src;

  const url = new URL(src);
  url.pathname = url.pathname.replace(PUBLIC_OBJECT, RENDER_IMAGE);
  url.searchParams.set("width", String(width));
  // Supabase accepts 20-100 and defaults to 80; Next's default is 75.
  url.searchParams.set("quality", String(quality ?? 75));
  return url.toString();
}
