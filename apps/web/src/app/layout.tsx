import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SimForge",
  description: "Tier-1 governance & certification platform for Village OS agents",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
