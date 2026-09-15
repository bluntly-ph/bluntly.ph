"use client";

import { useState } from "react";
import { Export } from "@phosphor-icons/react/dist/ssr";

/**
 * The profile panel's 20px Export control (Figma 5446:5891). Shares the
 * public profile address — `/u/{id}`, not the owner's private `/profile` —
 * through the platform sheet, or copies it where there is none.
 */
export function ProfileShareButton({ name, path }: { name: string; path: string }) {
  const [copied, setCopied] = useState(false);

  async function share() {
    const url = new URL(path, window.location.origin).toString();
    try {
      if (navigator.share) {
        await navigator.share({ title: `${name} on bluntly`, url });
        return;
      }
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* dismissed sheet or blocked clipboard: nothing to report */
    }
  }

  return (
    <button
      type="button"
      onClick={share}
      aria-label="Share this profile"
      className="grid h-11 w-11 cursor-pointer place-items-center rounded-full text-[var(--text-primary)] hover:bg-[var(--line-hairline-10)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-primary)]"
    >
      <Export size={20} aria-hidden="true" />
      <span role="status" className="sr-only">
        {copied ? "Profile link copied" : ""}
      </span>
    </button>
  );
}

export default ProfileShareButton;
