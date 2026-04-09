import { useAuth0 } from "@auth0/auth0-react";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { AuthScreen } from "../components/AuthScreen";

type ProtectedRouteProps = {
  children: ReactNode;
};

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const { isAuthenticated, isLoading } = useAuth0();
  const location = useLocation();

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
    const returnTo = `${location.pathname}${location.search}${location.hash}`;
    return <Navigate to="/login" replace state={{ returnTo }} />;
  }

  return <>{children}</>;
}
