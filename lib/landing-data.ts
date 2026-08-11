import type { Icon } from "@phosphor-icons/react";
import {
  Basketball,
  Briefcase,
  CarProfile,
  Circuitry,
  Dress,
  Eye,
  GameController,
  HairDryer,
  Heartbeat,
  House,
  Lamp,
  Lego,
  PawPrint,
  Pizza,
  SealCheck,
  Sparkle,
  TrendUp,
  UserCircleCheck,
} from "@phosphor-icons/react/dist/ssr";

/**
 * Landing-page content.
 *
 * The reviews here are curated sample content that matches the Figma frame. The
 * public list surfaces need a feed endpoint that joins review + author + product
 * (which the API does not expose yet — the reviews list returns neither author
 * display data nor product names). Everything a real feed would fill is confined
 * to `FEATURED_REVIEWS` / `READING_REVIEWS` so swapping in that endpoint later is
 * a single-function change, not a rewrite of the components.
 */

export type Category = {
  slug: string;
  label: string;
  icon: Icon;
};

/** The "What people are reading" tab row, in the frame's order. Trending leads. */
export const CATEGORIES: Category[] = [
  { slug: "trending", label: "Trending", icon: TrendUp },
  { slug: "automotive", label: "Automotive", icon: CarProfile },
  { slug: "beauty", label: "Beauty", icon: HairDryer },
  { slug: "electronics-tech", label: "Electronics & Tech", icon: Circuitry },
  { slug: "fashion-accessories", label: "Fashion & Accessories", icon: Dress },
  { slug: "food", label: "Food", icon: Pizza },
  { slug: "gaming", label: "Gaming", icon: GameController },
  { slug: "health-fitness", label: "Health & Fitness", icon: Heartbeat },
  { slug: "home-appliances", label: "Home Appliances", icon: Lamp },
  { slug: "home-living", label: "Home & Living", icon: House },
  { slug: "kids-toys", label: "Kids & Toys", icon: Lego },
  { slug: "office-productivity", label: "Office & Productivity", icon: Briefcase },
  { slug: "sports-outdoors", label: "Sports & Outdoors", icon: Basketball },
  { slug: "pets", label: "Pets", icon: PawPrint },
];

export type ReviewCardData = {
  id: string;
  author: string;
  /** A hue for the placeholder avatar until real avatars are wired. */
  authorHue: number;
  ageLabel: string;
  /**
   * The product this review is about, rendered bold above the title (BUG-006).
   * The two used to arrive as one undifferentiated string, so a card gave no
   * way to tell what was being reviewed from what the reviewer concluded.
   */
  product?: string | null;
  title: string;
  upvotes: string;
  comments: string;
  /** A hue for the branded placeholder shown when a review has no photo. */
  imageHue: number;
  /** The reviewer's submitted photo, when there is one. */
  imageUrl?: string | null;
};

export const READING_REVIEWS: ReviewCardData[] = [
  {
    id: "jisulife-fan",
    author: "viole",
    authorHue: 18,
    ageLabel: "12d",
    title: "Jisulife Handheld Fan Life9 — Worth the money or just overhyped?",
    upvotes: "14.8k",
    comments: "3.2k",
    imageHue: 20,
  },
  {
    id: "macbook-air-m2",
    author: "viole",
    authorHue: 210,
    ageLabel: "12d",
    title: "Macbook Air M2 — Lightweight beast!",
    upvotes: "14.8k",
    comments: "3.2k",
    imageHue: 265,
  },
  {
    id: "akko-5075",
    author: "viole",
    authorHue: 150,
    ageLabel: "12d",
    title:
      "Akko 5075 Plus — The best budget keyboard in the world! This changed how I type.",
    upvotes: "14.8k",
    comments: "3.2k",
    imageHue: 340,
  },
  {
    id: "jisulife-noisy",
    author: "viole",
    authorHue: 42,
    ageLabel: "12d",
    title: "Jisulife Handheld Fan Life9 — Overpriced & too noisy!",
    upvotes: "14.8k",
    comments: "3.2k",
    imageHue: 6,
  },
  {
    id: "anker-powerbank",
    author: "andreo",
    authorHue: 280,
    ageLabel: "8d",
    title: "Anker 737 Power Bank — Charges everything, survives everything.",
    upvotes: "9.1k",
    comments: "1.4k",
    imageHue: 190,
  },
];

/** The big card floating over the hero. */
export const FEATURED_REVIEW = {
  author: "yuceann",
  trust: "100",
  ageLabel: "5h",
  title: "Jisulife Handheld Fan Life9 — Worth the money or just overhyped?",
  excerpt:
    "When you're living in a tropical country such as the Philippines, you understand well that it gets hot. And by hot, we mean hot-hot. It's even worse…",
  question: "How noisy is it?",
  earned: "Earned ₱45.50 today",
};

export type TrustPoint = { icon: Icon; text: string };

export const TRUST_POINTS: TrustPoint[] = [
  { icon: SealCheck, text: "No paid placements. No fake opinions." },
  {
    icon: UserCircleCheck,
    text: "We require proof of purchase for all affiliate reviews.",
  },
  { icon: Sparkle, text: "Brands can't pay to influence what people say." },
  { icon: Eye, text: "Every reviewer's earnings and history are public." },
];

export const FOOTER_LINKS = {
  about: [
    { label: "About us", href: "/about" },
    { label: "Contact us", href: "/contact" },
    { label: "How bluntly works", href: "/how-it-works" },
    { label: "FAQs", href: "/faqs" },
    { label: "Articles", href: "/articles" },
  ],
  read: [
    { label: "Privacy Policy", href: "/privacy" },
    { label: "Terms & Conditions", href: "/terms" },
    { label: "Community Guidelines", href: "/guidelines" },
    { label: "Legal", href: "/legal" },
  ],
};
