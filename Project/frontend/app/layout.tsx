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
  title: "ImpactIQ: Understand Every Change Before It Happens",
  description: "See what a story, epic or sprint backlog affects before you plan the sprint.",
};

// Runs before first paint so a saved light theme never flashes dark.
const themeScript = `try{var t=localStorage.getItem("cip-theme");if(t!=="light"&&t!=="dark")t=matchMedia("(prefers-color-scheme: light)").matches?"light":"dark";var e=document.documentElement;e.dataset.theme=t;e.classList.toggle("dark",t==="dark")}catch(_){}`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${monaSans.variable} dark h-full antialiased`}
      data-theme="dark"
      suppressHydrationWarning
    >
      <head><script dangerouslySetInnerHTML={{ __html: themeScript }} /></head>
      <body><AppShell>{children}</AppShell></body>
    </html>
  );
}
