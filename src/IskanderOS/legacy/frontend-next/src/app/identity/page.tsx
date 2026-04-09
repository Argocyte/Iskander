/**
 * Identity Page — Wallet connection, SBT info, trust score, role.
 *
 * Replaces frontend/pages/identity.py. Uses RainbowKit ConnectButton
 * and reads CoopIdentity SBT data via SIWE auth.
 */
"use client";

import { ConnectButton } from "@rainbow-me/rainbowkit";
import { useAccount } from "wagmi";
import { useAuth } from "@/hooks/useAuth";

export default function IdentityPage() {
  const { address, isConnected } = useAccount();
  const { user, isAuthenticated, login, isLoading } = useAuth();

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <h1 className="text-2xl font-bold text-iskander-200">Cooperative Identity</h1>

      {/* Wallet Connection */}
      <div className="bg-iskander-900 rounded-xl p-6 border border-iskander-800">
        <h2 className="text-lg font-semibold text-iskander-300 mb-4">
          Wallet Connection
        </h2>
        <ConnectButton />

        {isConnected && !isAuthenticated && (
          <div className="mt-4">
            <p className="text-iskander-400 text-sm mb-3">
              Wallet connected. Sign in with Ethereum to access your cooperative membership.
            </p>
            <button
              onClick={login}
              disabled={isLoading}
              className="px-4 py-2 bg-iskander-600 text-white rounded-lg hover:bg-iskander-500 transition-colors disabled:opacity-50"
            >
              {isLoading ? "Signing..." : "Sign In with Ethereum"}
            </button>
          </div>
        )}
      </div>

      {/* Member Card */}
      {isAuthenticated && user && (
        <div className="bg-iskander-900 rounded-xl p-6 border border-iskander-800">
          <h2 className="text-lg font-semibold text-iskander-300 mb-4">
            Member Profile
          </h2>
          <div className="space-y-3">
            <ProfileField label="Address" value={user.address} mono />
            <ProfileField
              label="DID"
              value={user.did || "Not assigned (guest)"}
              mono={!!user.did}
            />
            <ProfileField label="Role" value={user.role} />
            <ProfileField label="Trust Score" value={`${user.trustScore} / 1000`} />
            <ProfileField
              label="SBT Token ID"
              value={user.memberTokenId?.toString() || "None"}
            />
            <ProfileField
              label="Membership"
              value={user.isMember ? "Active Member" : "Guest / Off-chain"}
            />
            <ProfileField label="Chain ID" value={String(user.chainId)} />
            <ProfileField
              label="Wallet Type"
              value={user.isSmartContract ? "Smart Contract (Safe)" : "EOA"}
            />
          </div>
        </div>
      )}

      {/* ICA Principles Reminder */}
      <div className="bg-iskander-950 rounded-xl p-4 border border-iskander-800">
        <p className="text-xs text-iskander-600">
          Identity is governed by ERC-4973 Account-Bound Tokens (Soulbound).
          Membership is non-transferable and tied to your cooperative participation.
          BrightID provides Sybil resistance without KYC.
        </p>
      </div>
    </div>
  );
}

function ProfileField({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex justify-between items-center py-2 border-b border-iskander-800 last:border-0">
      <span className="text-sm text-iskander-500">{label}</span>
      <span
        className={`text-sm text-iskander-200 ${
          mono ? "font-mono text-xs" : "font-medium capitalize"
        }`}
      >
        {value}
      </span>
    </div>
  );
}
