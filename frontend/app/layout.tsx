import type { Metadata } from "next";
import Link from "next/link";
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
      <body className="antialiased">
        {/* Step 12b-3 -- top nav, shown on every page since it lives here
            in the root layout. next/link does client-side navigation
            (no full page reload) instead of a plain <a> tag's hard
            reload. */}
        <nav className="border-b border-gray-200 bg-white">
          <div className="mx-auto flex max-w-5xl items-center gap-6 px-6 py-4">
            <span className="text-sm font-bold uppercase tracking-wide text-gray-400">
              MSME Credit AI
            </span>
            <Link href="/" className="text-sm font-medium text-gray-700 hover:text-blue-600">
              Evaluate
            </Link>
            <Link
              href="/portfolio"
              className="text-sm font-medium text-gray-700 hover:text-blue-600"
            >
              Portfolio
            </Link>
            <Link
              href="/fairness"
              className="text-sm font-medium text-gray-700 hover:text-blue-600"
            >
              Fairness Audit
            </Link>
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}
