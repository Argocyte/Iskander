/**
 * Root Layout — Phase 19: Next.js App Router Layout.
 *
 * Wraps all pages with Web3 providers, sidebar navigation, and header.
 */
import type { Metadata } from "next";
import { WagmiProvider } from "@/components/providers/WagmiProvider";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import "./globals.css";

export const metadata: Metadata = {
  title: "Iskander Node — Sovereign Cooperative OS",
  description:
    "Agentic AI operating system for DisCOs and Platform Co-ops. " +
    "Implements the Solidarity Stack and ICA Principles.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <WagmiProvider>
          <div className="flex min-h-screen">
            <Sidebar />
            <div className="flex-1 flex flex-col">
              <Header />
              <main className="flex-1 p-6">{children}</main>
            </div>
          </div>
        </WagmiProvider>
      </body>
    </html>
  );
}
