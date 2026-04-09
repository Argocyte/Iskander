/**
 * useAuth.ts — Phase 19: SIWE Authentication Hook.
 *
 * Manages the SIWE login flow:
 *   1. POST /auth/nonce → get server nonce
 *   2. Sign SIWE message with connected wallet
 *   3. POST /auth/login → receive JWT
 *   4. Store tokens, auto-refresh before expiry
 */
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAccount, useSignMessage } from "wagmi";
import { SiweMessage } from "siwe";
import { auth, setAccessToken } from "@/lib/api";
import { chainId } from "@/lib/wagmiConfig";

export interface UserProfile {
  address: string;
  did: string | null;
  role: string;
  memberTokenId: number | null;
  trustScore: number;
  isMember: boolean;
  isSmartContract: boolean;
  chainId: number;
}

interface AuthState {
  user: UserProfile | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
}

export function useAuth() {
  const { address, isConnected } = useAccount();
  const { signMessageAsync } = useSignMessage();

  const [state, setState] = useState<AuthState>({
    user: null,
    isAuthenticated: false,
    isLoading: false,
    error: null,
  });

  const refreshTokenRef = useRef<string | null>(null);
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Clean up refresh timer on unmount.
  useEffect(() => {
    return () => {
      if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    };
  }, []);

  // Auto-logout when wallet disconnects.
  useEffect(() => {
    if (!isConnected && state.isAuthenticated) {
      logout();
    }
  }, [isConnected]);

  /**
   * Full SIWE login flow.
   */
  const login = useCallback(async () => {
    if (!address || !isConnected) {
      setState((s) => ({ ...s, error: "Wallet not connected" }));
      return;
    }

    setState((s) => ({ ...s, isLoading: true, error: null }));

    try {
      // 1. Get nonce from server.
      const { nonce } = await auth.getNonce();

      // 2. Create SIWE message.
      const siweMessage = new SiweMessage({
        domain: window.location.host,
        address,
        statement: "Sign in to Iskander Node — your cooperative sovereign OS.",
        uri: window.location.origin,
        version: "1",
        chainId,
        nonce,
      });

      const message = siweMessage.prepareMessage();

      // 3. Sign with wallet.
      const signature = await signMessageAsync({ message });

      // 4. Submit to backend.
      const response = await auth.login(message, signature);

      // 5. Store tokens.
      setAccessToken(response.access_token);
      refreshTokenRef.current = response.refresh_token;

      // 6. Schedule auto-refresh (refresh at 90% of expiry time).
      const refreshIn = response.expires_in * 0.9 * 1000;
      scheduleRefresh(refreshIn);

      // 7. Update state.
      const user: UserProfile = {
        address: response.user.address,
        did: response.user.did,
        role: response.user.role,
        memberTokenId: response.user.member_token_id,
        trustScore: response.user.trust_score,
        isMember: response.user.is_member,
        isSmartContract: response.user.is_smart_contract,
        chainId: response.user.chain_id,
      };

      setState({
        user,
        isAuthenticated: true,
        isLoading: false,
        error: null,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Login failed";
      setState({ user: null, isAuthenticated: false, isLoading: false, error: message });
      setAccessToken(null);
    }
  }, [address, isConnected, signMessageAsync]);

  /**
   * Logout: revoke refresh token and clear state.
   */
  const logout = useCallback(async () => {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);

    if (refreshTokenRef.current) {
      try {
        await auth.logout(refreshTokenRef.current);
      } catch {
        // Ignore errors during logout.
      }
    }

    setAccessToken(null);
    refreshTokenRef.current = null;
    setState({ user: null, isAuthenticated: false, isLoading: false, error: null });
  }, []);

  /**
   * Silently refresh the access token.
   */
  const refreshAccessToken = useCallback(async () => {
    if (!refreshTokenRef.current) return;

    try {
      const response = await auth.refresh(refreshTokenRef.current);
      setAccessToken(response.access_token);
      scheduleRefresh(response.expires_in * 0.9 * 1000);
    } catch {
      // Refresh failed — force re-login.
      logout();
    }
  }, [logout]);

  function scheduleRefresh(delayMs: number) {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    refreshTimerRef.current = setTimeout(refreshAccessToken, delayMs);
  }

  return {
    ...state,
    login,
    logout,
    refreshAccessToken,
  };
}
