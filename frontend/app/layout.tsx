import type { Metadata } from "next";
import { Instrument_Sans } from "next/font/google";
import { AppShell } from "@/components/shell/app-shell";
import "./globals.css";

const instrumentSans = Instrument_Sans({
  variable: "--font-instrument-sans",
  subsets: ["latin"],
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
      className={`${instrumentSans.variable} dark h-full antialiased`}
    >
      <body><AppShell>{children}</AppShell></body>
    </html>
  );
}
