/**
 * WagmiProvider.tsx — Phase 19: Root Web3 Provider.
 *
 * Wraps the app with Wagmi, RainbowKit, and React Query providers.
 * Configured for Gnosis Chain (production) and Anvil (development).
 */
"use client";

import { RainbowKitProvider, darkTheme } from "@rainbow-me/rainbowkit";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { WagmiProvider as WagmiCoreProvider } from "wagmi";
import { config } from "@/lib/wagmiConfig";

import "@rainbow-me/rainbowkit/styles.css";

const queryClient = new QueryClient();

export function WagmiProvider({ children }: { children: React.ReactNode }) {
  return (
    <WagmiCoreProvider config={config}>
      <QueryClientProvider client={queryClient}>
        <RainbowKitProvider
          theme={darkTheme({
            accentColor: "#0ea5e9",
            accentColorForeground: "white",
            borderRadius: "medium",
          })}
          appInfo={{
            appName: "Iskander Node",
            learnMoreUrl: "https://iskander.coop",
          }}
        >
          {children}
        </RainbowKitProvider>
      </QueryClientProvider>
    </WagmiCoreProvider>
  );
}
