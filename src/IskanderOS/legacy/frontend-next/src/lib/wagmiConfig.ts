/**
 * wagmiConfig.ts — Phase 19: Wagmi v2 + RainbowKit Configuration.
 *
 * Defines chain configurations for Gnosis Chain (production) and Anvil (development).
 * Configures wallet connectors: MetaMask, WalletConnect, Safe.
 */
import { getDefaultConfig } from "@rainbow-me/rainbowkit";
import { http, type Chain } from "viem";
import { gnosis } from "viem/chains";

// ── Anvil Local Dev Chain ────────────────────────────────────────────────────

const anvil: Chain = {
  id: 31337,
  name: "Anvil (Local)",
  nativeCurrency: { name: "Ether", symbol: "ETH", decimals: 18 },
  rpcUrls: {
    default: { http: ["http://localhost:8545"] },
  },
  testnet: true,
};

// ── Chain Selection ──────────────────────────────────────────────────────────

const chainId = parseInt(process.env.NEXT_PUBLIC_CHAIN_ID || "31337", 10);
const isDev = chainId === 31337;

const chains: readonly [Chain, ...Chain[]] = isDev
  ? [anvil, gnosis]
  : [gnosis, anvil];

// ── Wagmi + RainbowKit Config ────────────────────────────────────────────────

export const config = getDefaultConfig({
  appName: "Iskander Node",
  projectId: process.env.NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID || "PLACEHOLDER",
  chains,
  transports: {
    [gnosis.id]: http("https://rpc.gnosischain.com"),
    [anvil.id]: http("http://localhost:8545"),
  },
  ssr: true,
});

export { chains, isDev, chainId };
