import type { Metadata } from "next";

import { NavLink } from "@/components/nav-link";

import "./globals.css";

export const metadata: Metadata = {
  title: "Rackmind",
  description: "Data center monitoring: live telemetry, incidents and AI diagnosis.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full flex-col">
        <header className="border-b border-line bg-surface">
          <div className="mx-auto flex h-14 w-full max-w-7xl items-center gap-8 px-4">
            <span className="text-base font-semibold tracking-tight">Rackmind</span>
            <nav className="flex gap-1 text-sm">
              <NavLink href="/">Racks</NavLink>
            </nav>
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
