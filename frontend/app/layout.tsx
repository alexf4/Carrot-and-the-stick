import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Playfair_Display, DM_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import styles from "./layout.module.css";

const playfair = Playfair_Display({
  subsets: ["latin"],
  variable: "--font-display",
  weight: ["400", "700"],
  display: "swap",
});

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-body",
  weight: ["400", "500", "600"],
  display: "swap",
});

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

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={`${playfair.variable} ${dmSans.variable} ${jetbrainsMono.variable}`}>
      <body style={{ fontFamily: "var(--font-body, sans-serif)" }}>
        <div className={styles.body}>
          <header className={styles.header}>
            <a href="/" className={styles.logo}>
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
