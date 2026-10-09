import type { Metadata } from "next";
import "./globals.css";

// Note: a standard `create-next-app` scaffold also wires up next/font here
// (usually the Geist font family). That's skipped in this hand-written
// scaffold on purpose -- it fetches font files from Google Fonts at BUILD
// time, which adds a network dependency we don't need for this project's
// purposes. Tailwind's default system font stack (set in globals.css) is
// simpler and works offline. Add next/font back later if a specific look
// is wanted.
export const metadata: Metadata = {
  title: "MSME Alternative Credit Assessment",
  description:
    "Explainable AI credit scoring for MSMEs with thin credit files, using alternative data (bank transactions, GST filings, UPI/digital payments).",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
