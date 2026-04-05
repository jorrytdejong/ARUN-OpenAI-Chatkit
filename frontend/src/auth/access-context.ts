import { createContext, useContext } from "react";

export type AccessSnapshot = {
  auth0_user_id: string;
  has_access: boolean;
  stripe_customer_id: string | null;
  stripe_subscription_id: string | null;
  stripe_price_id: string | null;
  stripe_subscription_status: string | null;
  current_period_end: string | null;
  can_manage_billing: boolean;
};

export type AccessContextValue = {
  access: AccessSnapshot | null;
  error: string | null;
  isLoading: boolean;
  authorizedFetch: typeof fetch;
  refreshAccess: () => Promise<AccessSnapshot | null>;
};

export const AccessContext = createContext<AccessContextValue | null>(null);

export function useAccess() {
  const context = useContext(AccessContext);
  if (context === null) {
    throw new Error("useAccess must be used within an AccessProvider");
  }
  return context;
}
