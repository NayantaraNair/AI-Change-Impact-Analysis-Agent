import type { Metadata } from "next";
import { Mona_Sans } from "next/font/google";
import { AppShell } from "@/components/shell/app-shell";
import "./globals.css";

const monaSans = Mona_Sans({
  variable: "--font-mona-sans",
  subsets: ["latin"],
  axes: ["wdth"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Change Impact Copilot",
  description: "Understand the blast radius, risk, and release readiness of banking changes.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${monaSans.variable} dark h-full antialiased`}
    >
      <body><AppShell>{children}</AppShell></body>
    </html>
  );
}
