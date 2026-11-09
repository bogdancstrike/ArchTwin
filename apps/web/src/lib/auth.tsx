import { InMemoryWebStorage, WebStorageStateStore } from "oidc-client-ts";
import { useEffect, useLayoutEffect, type ReactNode } from "react";
import { AuthProvider, useAuth } from "react-oidc-context";

/** OIDC Authorization Code + PKCE (Keycloak); tokens live in memory only (AT-IDENTITY_POLICY-001). */
export const oidcConfig = {
  authority: import.meta.env.VITE_OIDC_AUTHORITY ?? "http://localhost:8280/realms/archtwin",
  client_id: import.meta.env.VITE_OIDC_CLIENT_ID ?? "archtwin-web",
  redirect_uri: `${window.location.origin}/`,
  post_logout_redirect_uri: `${window.location.origin}/`,
  scope: "openid profile email",
  automaticSilentRenew: true,
  userStore: new WebStorageStateStore({ store: new InMemoryWebStorage() }),
  onSigninCallback: () => {
    const back = sessionStorage.getItem("at-return-to");
    sessionStorage.removeItem("at-return-to");
    window.history.replaceState(window.history.state, document.title, back ?? window.location.pathname);
  },
};

let token: string | undefined;
let renew: (() => Promise<string | undefined>) | null = null;
export const getToken = () => token;
export const renewToken = () => (renew ? renew().catch(() => undefined) : Promise.resolve(token));

function Bridge({ children }: { children: ReactNode }) {
  const auth = useAuth();
  useLayoutEffect(() => {
    token = auth.user?.access_token;
    renew = async () => (await auth.signinSilent())?.access_token;
  }, [auth]);
  useEffect(() => {
    if (!auth.isLoading && !auth.isAuthenticated && !auth.activeNavigator && !auth.error) {
      sessionStorage.setItem("at-return-to", window.location.pathname + window.location.search);
      void auth.signinRedirect({ redirectMethod: "replace" });
    }
  }, [auth]);
  if (auth.error) return <div className="p-8 text-bad">Sign-in failed: {auth.error.message}</div>;
  if (!auth.isAuthenticated) return <div className="grid h-full place-items-center text-soft">Signing in…</div>;
  return <>{children}</>;
}

export function ArchTwinAuth({ children }: { children: ReactNode }) {
  return <AuthProvider {...oidcConfig}><Bridge>{children}</Bridge></AuthProvider>;
}
