import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAccess } from "./access-context";
import { AuthScreen } from "../components/AuthScreen";

type PaidRouteProps = {
  children: ReactNode;
};

export function PaidRoute({ children }: PaidRouteProps) {
  const { access, error, isLoading } = useAccess();

  if (isLoading) {
    return (
      <AuthScreen
        eyebrow="Checking plan"
        title="Confirming your subscription"
        description="One moment while we verify your access to the coach."
      />
    );
  }

  if (error) {
    return (
      <AuthScreen
        eyebrow="Access check failed"
        title="We couldn't confirm your subscription"
        description={error}
      />
    );
  }

  if (!access?.has_access) {
    return <Navigate to="/subscribe" replace />;
  }

  return <>{children}</>;
}
