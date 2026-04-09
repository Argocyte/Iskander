/**
 * Header.tsx — Phase 19: Top Header with Wallet Connection.
 *
 * Shows RainbowKit ConnectButton and SIWE login status.
 */
"use client";

import { ConnectButton } from "@rainbow-me/rainbowkit";
import { useAuth } from "@/hooks/useAuth";

export function Header() {
  const { user, isAuthenticated, isLoading, error, login, logout } = useAuth();

  return (
    <header className="h-16 bg-iskander-950 border-b border-iskander-800 px-6 flex items-center justify-between">
      <div className="flex items-center gap-4">
        {isAuthenticated && user && (
          <div className="flex items-center gap-2 text-sm">
            <span className="text-iskander-400">Role:</span>
            <span className="text-iskander-200 font-medium capitalize">
              {user.role}
            </span>
            {user.trustScore > 0 && (
              <>
                <span className="text-iskander-600">|</span>
                <span className="text-iskander-400">Trust:</span>
                <span className="text-iskander-200">{user.trustScore}/1000</span>
              </>
            )}
          </div>
        )}
        {error && (
          <span className="text-red-400 text-xs">{error}</span>
        )}
      </div>

      <div className="flex items-center gap-3">
        {isAuthenticated ? (
          <button
            onClick={logout}
            className="px-3 py-1.5 text-xs bg-iskander-800 text-iskander-300 rounded hover:bg-iskander-700 transition-colors"
          >
            Sign Out
          </button>
        ) : (
          <button
            onClick={login}
            disabled={isLoading}
            className="px-3 py-1.5 text-xs bg-iskander-600 text-white rounded hover:bg-iskander-500 transition-colors disabled:opacity-50"
          >
            {isLoading ? "Signing in..." : "Sign In (SIWE)"}
          </button>
        )}
        <ConnectButton
          showBalance={false}
          chainStatus="icon"
          accountStatus="avatar"
        />
      </div>
    </header>
  );
}
