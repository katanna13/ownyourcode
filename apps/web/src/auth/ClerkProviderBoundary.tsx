import { ClerkProvider, useAuth, useClerk } from "@clerk/react";
import { ReactNode, createContext, useContext, useMemo, useState } from "react";

export type AuthenticationState = {
  isConfigured: boolean;
  isLoaded: boolean;
  isSignedIn: boolean;
  sessionExpired: boolean;
  getToken: () => Promise<string | null>;
  signOut: () => Promise<void>;
  markSessionExpired: () => void;
};

const unavailableAuthentication: AuthenticationState = {
  isConfigured: false,
  isLoaded: true,
  isSignedIn: false,
  sessionExpired: false,
  getToken: async () => null,
  signOut: async () => undefined,
  markSessionExpired: () => undefined
};

const AuthenticationContext = createContext<AuthenticationState>(unavailableAuthentication);

function publishableKey(): string | null {
  const value = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY?.trim();
  return value || null;
}

function ClerkAuthenticationBridge({ children }: { children: ReactNode }) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const { signOut } = useClerk();
  const [sessionExpired, setSessionExpired] = useState(false);
  const state = useMemo<AuthenticationState>(() => ({
    isConfigured: true,
    isLoaded,
    isSignedIn: Boolean(isSignedIn) && !sessionExpired,
    sessionExpired,
    getToken: async () => getToken(),
    signOut: async () => signOut(),
    markSessionExpired: () => setSessionExpired(true)
  }), [getToken, isLoaded, isSignedIn, sessionExpired, signOut]);

  return <AuthenticationContext.Provider value={state}>{children}</AuthenticationContext.Provider>;
}

export function ClerkProviderBoundary({ children }: { children: ReactNode }) {
  const key = publishableKey();
  if (!key) {
    return (
      <AuthenticationContext.Provider value={unavailableAuthentication}>
        {children}
      </AuthenticationContext.Provider>
    );
  }

  return (
    <ClerkProvider publishableKey={key}>
      <ClerkAuthenticationBridge>{children}</ClerkAuthenticationBridge>
    </ClerkProvider>
  );
}

export function useAuthentication(): AuthenticationState {
  return useContext(AuthenticationContext);
}

export function AuthenticationTestProvider({
  children,
  value
}: {
  children: ReactNode;
  value: Partial<AuthenticationState>;
}) {
  const state = { ...unavailableAuthentication, ...value };
  return <AuthenticationContext.Provider value={state}>{children}</AuthenticationContext.Provider>;
}
