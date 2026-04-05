import {
  Auth0Provider,
  type AppState,
} from "@auth0/auth0-react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import {
  AUTH0_AUDIENCE,
  AUTH0_CLIENT_ID,
  AUTH0_DOMAIN,
} from "../lib/config";

type Auth0ProviderWithNavigateProps = {
  children: ReactNode;
};

type RedirectAppState = AppState & {
  returnTo?: string;
};

export function Auth0ProviderWithNavigate({
  children,
}: Auth0ProviderWithNavigateProps) {
  const navigate = useNavigate();

  const handleRedirectCallback = (appState?: RedirectAppState) => {
    void navigate(appState?.returnTo ?? "/", { replace: true });
  };

  return (
    <Auth0Provider
      domain={AUTH0_DOMAIN}
      clientId={AUTH0_CLIENT_ID}
      authorizationParams={{
        audience: AUTH0_AUDIENCE,
        redirect_uri: `${window.location.origin}/login`,
      }}
      onRedirectCallback={handleRedirectCallback}
    >
      {children}
    </Auth0Provider>
  );
}
