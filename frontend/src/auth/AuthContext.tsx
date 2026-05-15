import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ReactNode,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import { api } from '../api/client';
import type { AuthConfig, CurrentUser } from '../api/types';
import { setAuthHeadersProvider } from './auth-bridge';

const AUTH_STORAGE_KEY = 'researchops:auth:dev-email';

type AuthContextValue = {
  user: CurrentUser | null;
  config: AuthConfig | null;
  authMode: string;
  isLoading: boolean;
  isAuthenticated: boolean;
  loginAsDevUser: (email: string) => void;
  setEntraAccessToken: (token: string | null) => void;
  logout: () => void;
  hasRole: (...roles: string[]) => boolean;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function readStoredDevEmail(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage.getItem(AUTH_STORAGE_KEY);
  } catch {
    return null;
  }
}

function isCurrentUser(value: unknown): value is CurrentUser {
  if (!value || typeof value !== 'object') return false;
  const data = value as Record<string, unknown>;
  return (
    typeof data.id === 'string'
    && typeof data.email === 'string'
    && Array.isArray(data.roles)
  );
}

function isAuthConfig(value: unknown): value is AuthConfig {
  if (!value || typeof value !== 'object') return false;
  return typeof (value as Record<string, unknown>).auth_mode === 'string';
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [devEmail, setDevEmail] = useState<string | null>(() => readStoredDevEmail());
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const devEmailRef = useRef<string | null>(devEmail);
  const accessTokenRef = useRef<string | null>(accessToken);
  const modeRef = useRef<string>('development');

  const configQuery = useQuery({
    queryKey: ['auth-config'],
    queryFn: () => api.getAuthConfig(),
    staleTime: Number.POSITIVE_INFINITY,
    retry: false,
  });

  const config = isAuthConfig(configQuery.data) ? configQuery.data : null;
  const authMode = config?.auth_mode ?? 'development';

  useEffect(() => {
    devEmailRef.current = devEmail;
  }, [devEmail]);

  useEffect(() => {
    accessTokenRef.current = accessToken;
  }, [accessToken]);

  useEffect(() => {
    modeRef.current = authMode;
  }, [authMode]);

  useEffect(() => {
    setAuthHeadersProvider(() => {
      const headers: Record<string, string> = {};
      const mode = modeRef.current;
      if (mode === 'entra' && accessTokenRef.current) {
        headers.Authorization = `Bearer ${accessTokenRef.current}`;
      } else if (devEmailRef.current) {
        headers['X-Dev-User-Email'] = devEmailRef.current;
      }
      return headers;
    });
  }, []);

  const userQuery = useQuery({
    queryKey: ['auth-me', devEmail, accessToken, authMode],
    queryFn: () => api.getAuthMe(),
    retry: false,
  });

  const user = isCurrentUser(userQuery.data) ? userQuery.data : null;

  const loginAsDevUser = useCallback(
    (email: string) => {
      try {
        window.localStorage.setItem(AUTH_STORAGE_KEY, email);
      } catch {
        /* localStorage may be unavailable */
      }
      setDevEmail(email);
      void queryClient.invalidateQueries({ queryKey: ['auth-me'] });
    },
    [queryClient],
  );

  const setEntraAccessToken = useCallback(
    (token: string | null) => {
      setAccessToken(token);
      void queryClient.invalidateQueries({ queryKey: ['auth-me'] });
    },
    [queryClient],
  );

  const logout = useCallback(() => {
    try {
      window.localStorage.removeItem(AUTH_STORAGE_KEY);
    } catch {
      /* localStorage may be unavailable */
    }
    setDevEmail(null);
    setAccessToken(null);
    void queryClient.invalidateQueries({ queryKey: ['auth-me'] });
  }, [queryClient]);

  const hasRole = useCallback(
    (...roles: string[]) => {
      if (!user) return false;
      const userRoles = new Set(user.roles);
      return roles.some((role) => userRoles.has(role));
    },
    [user],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      config,
      authMode,
      isLoading: configQuery.isLoading || userQuery.isLoading,
      isAuthenticated: !!user,
      loginAsDevUser,
      setEntraAccessToken,
      logout,
      hasRole,
    }),
    [
      user,
      config,
      authMode,
      configQuery.isLoading,
      userQuery.isLoading,
      loginAsDevUser,
      setEntraAccessToken,
      logout,
      hasRole,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider.');
  }
  return ctx;
}
