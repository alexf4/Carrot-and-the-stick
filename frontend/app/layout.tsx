/**
 * Root layout — shared shell for every page in the application.
 *
 * This is a Next.js App Router root layout. It wraps every route with the
 * HTML skeleton, injects Google Fonts via `next/font` (self-hosted for
 * performance), and renders the global site header.
 *
 * Font strategy
 * -------------
 * Three fonts are loaded and exposed as CSS custom properties:
 *
 * - `--font-display` → Playfair Display (serif): used for page headings and
 *   the site logo. Chosen for its editorial gravitas — it signals that this
 *   is a serious accountability platform, not a generic civic app.
 * - `--font-body` → DM Sans: clean grotesque for all body text and UI chrome.
 * - `--font-mono` → JetBrains Mono: used exclusively for financial figures
 *   (dollar amounts, pool totals) to give them the feel of a financial ledger.
 *
 * `next/font/google` downloads and self-hosts fonts at build time — no
 * runtime requests to fonts.googleapis.com. The `variable` option injects
 * each font as a CSS custom property on the `<html>` element.
 *
 * Header design
 * -------------
 * The header is intentionally minimal: logo text + a divider + tagline.
 * No navigation links at this stage (the only public page is `/reps`).
 * The amber `&` in the logo is the only decorative element, reinforcing the
 * carrot/stick brand color without adding an icon or SVG.
 *
 * Global styles
 * -------------
 * `globals.css` is imported here (once, at the root) and provides:
 * - CSS custom properties for the design system (colors, radii).
 * - A base reset.
 * - Background gradient and noise texture on `body`.
 */

import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Playfair_Display, DM_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import styles from "./layout.module.css";

/** Playfair Display — serif display font for headings and the logo. */
const playfair = Playfair_Display({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["400", "700"],
  display: "swap",
});

/** DM Sans — clean grotesque for body text and UI chrome. */
const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-body",
  weight: ["400", "500", "600"],
  display: "swap",
});

/** JetBrains Mono — monospace font for financial figures. */
const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Carrot and the Stick",
  description: "Hold your representatives accountable with pledge-based civic action.",
};

/**
 * RootLayout — rendered once around every page.
 *
 * Injects the three font CSS variables onto `<html>` and renders the
 * persistent site header. The `--font-body` variable is applied inline to
 * `<body>` as a fallback; all component-level font usage goes through the
 * CSS custom properties defined in `globals.css`.
 *
 * @param children - The page component for the current route.
 */
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${playfair.variable} ${dmSans.variable} ${jetbrainsMono.variable}`}>
      <body style={{ fontFamily: "var(--font-body, sans-serif)" }}>
        <div className={styles.body}>
          <header className={styles.header}>
            <a href="/" className={styles.logo}>
              {/* Amber ampersand echoes the carrot color; kept as text not SVG for SEO */}
              Carrot <span className={styles.logoAccent}>&</span> the Stick
            </a>
            <span className={styles.tagline}>Congressional Accountability</span>
          </header>
          <main className={styles.main}>{children}</main>
        </div>
      </body>
    </html>
  );
}
