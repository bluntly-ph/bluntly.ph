import type { Metadata, Viewport } from "next";
import { Bebas_Neue, Poppins } from "next/font/google";
import { cookies } from "next/headers";
import "./globals.css";

import { MobileNav } from "@/components/site/MobileNav";

// Self-hosted by Next rather than the design system's Google Fonts @import, so
// there is no render-blocking third-party request. The weights are the ones the
// source file actually uses.
const poppins = Poppins({
  variable: "--font-poppins",
  subsets: ["latin"],
  weight: ["200", "300", "400", "500", "600", "700"],
  display: "swap",
});

const bebasNeue = Bebas_Neue({
  variable: "--font-bebas",
  subsets: ["latin"],
  weight: "400",
  display: "swap",
});

export const metadata: Metadata = {
  title: "bluntly — Finally. Honest reviews.",
  description:
    "Philippine product reviews you can trust. No sponsorships. No bias. Ever.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f2f2f2" },
    { media: "(prefers-color-scheme: dark)", color: "#202020" },
  ],
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Read the preference on the server and stamp it before first paint. Nothing
  // is written by client JS on load, so there is no flash to prevent.
  // With no cookie the attribute is omitted and CSS decides: light by default,
  // dark from the `lg` breakpoint up, matching how the design is drawn.
  const theme = (await cookies()).get("theme")?.value;
  const dataTheme = theme === "dark" || theme === "light" ? theme : undefined;

  return (
    <html
      lang="en"
      data-theme={dataTheme}
      className={`${poppins.variable} ${bebasNeue.variable} h-full`}
    >
      <body className="min-h-full flex flex-col">
        {children}
        <MobileNav />
      </body>
    </html>
  );
}
