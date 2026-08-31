import type { Metadata } from "next";
import { Cinzel, JetBrains_Mono, Inter } from "next/font/google";
import "./globals.css";

const display = Cinzel({ subsets: ["latin"], weight: ["600", "800", "900"], variable: "--font-display" });
const mono = JetBrains_Mono({ subsets: ["latin"], weight: ["400", "500", "700"], variable: "--font-mono" });
const body = Inter({ subsets: ["latin"], variable: "--font-body" });

export const metadata: Metadata = {
  title: "Agent Valley",
  description: "Summon a familiar. Watch an agent do it.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${display.variable} ${mono.variable} ${body.variable}`}>
        {children}
      </body>
    </html>
  );
}
