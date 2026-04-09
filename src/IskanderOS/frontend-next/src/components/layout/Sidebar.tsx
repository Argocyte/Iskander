/**
 * Sidebar.tsx — Phase 19: Navigation Sidebar.
 *
 * Mirrors the Streamlit sidebar navigation with all Iskander pages.
 */
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

const navItems = [
  { href: "/", label: "Home", icon: "🏠", ready: true },
  { href: "/identity", label: "Identity", icon: "🪪", ready: true },
  { href: "/governance", label: "Governance", icon: "🏛️", ready: true },
  { href: "/deliberation", label: "Deliberation", icon: "💬", ready: true },
  { href: "/treasury", label: "Treasury", icon: "💰", ready: true },
  { href: "/ledger", label: "DisCO Ledger", icon: "📒", ready: false },
  { href: "/escrow", label: "Escrow", icon: "🤝", ready: true },
  { href: "/arbitration", label: "Arbitration", icon: "⚖️", ready: false },
  { href: "/tasks", label: "Tasks", icon: "📋", ready: false },
  { href: "/chat", label: "Agent Chat", icon: "🤖", ready: true },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 bg-iskander-950 text-white min-h-screen p-4 flex flex-col">
      <div className="mb-8">
        <h1 className="text-xl font-bold text-iskander-300">Iskander Node</h1>
        <p className="text-xs text-iskander-500 mt-1">Sovereign Cooperative OS</p>
      </div>

      <nav className="flex-1 space-y-1">
        {navItems.map((item) =>
          item.ready ? (
            <Link
              key={item.href}
              href={item.href}
              className={clsx(
                "flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors",
                pathname === item.href
                  ? "bg-iskander-800 text-iskander-100"
                  : "text-iskander-400 hover:bg-iskander-900 hover:text-iskander-200"
              )}
            >
              <span className="text-base">{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          ) : (
            <span
              key={item.href}
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm opacity-40 cursor-default"
            >
              <span className="text-base">{item.icon}</span>
              <span>{item.label} (soon)</span>
            </span>
          )
        )}
      </nav>

      <div className="mt-auto pt-4 border-t border-iskander-800">
        <p className="text-xs text-iskander-600 text-center">
          7 ICA Principles &bull; Glass Box
        </p>
      </div>
    </aside>
  );
}
