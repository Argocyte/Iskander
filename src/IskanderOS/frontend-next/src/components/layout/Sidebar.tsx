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
  { href: "/", label: "Home", icon: "🏠" },
  { href: "/identity", label: "Identity", icon: "🪪" },
  { href: "/governance", label: "Governance", icon: "🏛️" },
  { href: "/deliberation", label: "Deliberation", icon: "💬" },
  { href: "/treasury", label: "Treasury", icon: "💰" },
  { href: "/ledger", label: "DisCO Ledger", icon: "📒" },
  { href: "/escrow", label: "Escrow", icon: "🤝" },
  { href: "/arbitration", label: "Arbitration", icon: "⚖️" },
  { href: "/tasks", label: "Tasks", icon: "📋" },
  { href: "/chat", label: "Agent Chat", icon: "🤖" },
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
        {navItems.map((item) => (
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
        ))}
      </nav>

      <div className="mt-auto pt-4 border-t border-iskander-800">
        <p className="text-xs text-iskander-600 text-center">
          7 ICA Principles &bull; Glass Box
        </p>
      </div>
    </aside>
  );
}
