"use client";

import { useEffect } from "react";

/**
 * Scrolls to the section the address names once it exists.
 *
 * /dashboard streams in behind its loading.tsx, so the browser's own jump to
 * `#history` happens while only the skeleton is in the document, and it does
 * not try again when the section arrives. History's "Historical Bill" pill
 * links to `/dashboard#history` and landed at the top of the page, 1,955px
 * above Payment history (measured at 390px, 2026-09-17). Rendered after the
 * sections, this runs once they are in place.
 */
export function ScrollToHash() {
  useEffect(() => {
    const id = decodeURIComponent(window.location.hash.slice(1));
    if (id) document.getElementById(id)?.scrollIntoView({ block: "start" });
  }, []);
  return null;
}
