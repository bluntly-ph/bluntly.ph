/**
 * The eight interest categories from onboarding step 2 ("What do you shop
 * for?"), in the frame's own order and wording.
 *
 * Slugs are what get stored on `users.interests` and are matched against
 * `products.category`, which is a free string rather than an enum.
 */
export type Interest = {
  slug: string;
  label: string;
  /** Inline SVG path data, 24x24 viewBox, stroked in currentColor. */
  icon: string;
};

export const INTERESTS: Interest[] = [
  {
    slug: "electronics-tech",
    label: "Electronics & Tech",
    icon: "M4 4h10l6 6v10a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1zm10 0v6h6M8 14h6M8 17h4",
  },
  {
    slug: "office-productivity",
    label: "Office & Productivity",
    icon: "M3 8h18v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V8zm6 0V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v3M3 13h18",
  },
  {
    slug: "audio",
    label: "Audio",
    icon: "M4 14v-2a8 8 0 0 1 16 0v2M4 14a2 2 0 0 1 2-2h1v6H6a2 2 0 0 1-2-2v-2zm16 0a2 2 0 0 0-2-2h-1v6h1a2 2 0 0 0 2-2v-2z",
  },
  {
    slug: "home-living",
    label: "Home & Living",
    icon: "M3 10.5 12 3l9 7.5M5 9.5V20a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9.5",
  },
  {
    slug: "beauty",
    label: "Beauty",
    icon: "M9 3h6l-1 5H10L9 3zm1 5h4v12a2 2 0 0 1-2 2 2 2 0 0 1-2-2V8zm-1 6h6",
  },
  {
    slug: "fashion-accessories",
    label: "Fashion & Accessories",
    icon: "M9 3h6m-6 0-4 4 3 3 1-1v12h6V9l1 1 3-3-4-4M9 3a3 3 0 0 0 6 0",
  },
  {
    slug: "automotive",
    label: "Automotive",
    icon: "M5 16v2a1 1 0 0 1-1 1H3v-3m0 0 2-6h14l2 6m-18 0h18m0 0v3h-1a1 1 0 0 1-1-1v-2M7 13h2m6 0h2",
  },
  {
    slug: "health-fitness",
    label: "Health & Fitness",
    icon: "M20.8 6.6a5 5 0 0 0-8.8-1.8A5 5 0 0 0 3.2 6.6C2 10 6 14 12 20c6-6 10-10 8.8-13.4z",
  },
];

/** The design asks the user to pick three. */
export const REQUIRED_INTERESTS = 3;
