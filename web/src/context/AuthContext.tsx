import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { setApiBase } from "../lib/api";

type Credentials = {
  apiUrl: string;
  controlToken: string;
  adminToken: string;
  actor: string;
};

type AuthContextValue = Credentials & {
  authenticated: boolean;
  save: (credentials: Credentials) => void;
  logout: () => void;
};

const STORAGE_KEY = "versionweaver.console.credentials";
const empty: Credentials = { apiUrl: "", controlToken: "", adminToken: "", actor: "ui-user" };

function readCredentials(): Credentials {
  try {
    const stored = sessionStorage.getItem(STORAGE_KEY);
    return stored ? ({ ...empty, ...JSON.parse(stored) } as Credentials) : empty;
  } catch {
    return empty;
  }
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [credentials, setCredentials] = useState<Credentials>(readCredentials);
  useEffect(() => setApiBase(credentials.apiUrl), [credentials.apiUrl]);

  const value = useMemo<AuthContextValue>(
    () => ({
      ...credentials,
      authenticated: Boolean(credentials.controlToken),
      save: (next) => {
        const normalized = { ...next, apiUrl: next.apiUrl.trim().replace(/\/$/, "") };
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
        setApiBase(normalized.apiUrl);
        setCredentials(normalized);
      },
      logout: () => {
        sessionStorage.removeItem(STORAGE_KEY);
        setApiBase("");
        setCredentials(empty);
      }
    }),
    [credentials]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
