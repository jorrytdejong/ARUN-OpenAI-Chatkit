import { useAuth0 } from "@auth0/auth0-react";
import { useEffect, useRef, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { AuthScreen } from "../components/AuthScreen";

type ProtectedRouteProps = {
  children: ReactNode;
};

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, loginWithRedirect } = useAuth0();
  const location = useLocation();
  const hasStartedRedirect = useRef(false);

  useEffect(() => {
    if (isLoading || isAuthenticated || hasStartedRedirect.current) {
      return;
    }

    hasStartedRedirect.current = true;
    const returnTo = `${location.pathname}${location.search}${location.hash}`;
    void loginWithRedirect({ appState: { returnTo } });
  }, [isAuthenticated, isLoading, location, loginWithRedirect]);

  if (isLoading) {
    return (
      <AuthScreen
        eyebrow="Checking access"
        title="Confirming your session"
        description="One moment while we verify your access to the coach."
        variant="minimal"
      />
    );
  }

  if (!isAuthenticated) {
    return (
      <AuthScreen
        eyebrow="Redirecting"
        title="Opening secure sign-in"
        description="One moment while we send you to the login flow."
        variant="minimal"
      />
    );
  }

  return <>{children}</>;
}
