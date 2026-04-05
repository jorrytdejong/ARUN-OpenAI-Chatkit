import { Navigate, useSearchParams } from "react-router-dom";
import { useEffect, useState } from "react";
import { AuthScreen } from "./AuthScreen";
import { useAccess } from "../auth/access-context";

type BillingUrlResponse = {
  url: string;
};

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    if (typeof payload.detail === "string" && payload.detail.length > 0) {
      return payload.detail;
    }
  } catch {
    // Fall through to a generic message.
  }
  return `Request failed with status ${response.status}`;
}

export function SubscribePage() {
  const { access, authorizedFetch, error, isLoading, refreshAccess } = useAccess();
  const [searchParams] = useSearchParams();
  const [pendingAction, setPendingAction] = useState<"checkout" | "portal" | null>(
    null,
  );
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    if (searchParams.get("checkout") !== "success") {
      return;
    }

    let cancelled = false;
    let timeoutId: number | undefined;
    let attempt = 0;

    const poll = async () => {
      if (cancelled) {
        return;
      }

      attempt += 1;
      const snapshot = await refreshAccess();
      if (snapshot?.has_access || attempt >= 15 || cancelled) {
        return;
      }

      timeoutId = window.setTimeout(() => {
        void poll();
      }, 2000);
    };

    void poll();

    return () => {
      cancelled = true;
      if (timeoutId !== undefined) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [searchParams, refreshAccess]);

  if (isLoading) {
    return (
      <AuthScreen
        eyebrow="Loading plan"
        title="Checking your billing access"
        description="One moment while we fetch your subscription status."
      />
    );
  }

  if (error) {
    return (
      <AuthScreen
        eyebrow="Access unavailable"
        title="We couldn't load your billing status"
        description={error}
      />
    );
  }

  if (access?.has_access) {
    return <Navigate to="/" replace />;
  }

  const subscriptionStatus = access?.stripe_subscription_status;
  const detailText =
    subscriptionStatus === "past_due"
      ? "Your subscription needs attention before chat access can resume."
      : subscriptionStatus === "canceled"
        ? "Your subscription is no longer active. Start a new plan to re-enter the coach."
        : "Start the monthly plan to unlock the Meditative Juice Coach.";

  const beginCheckout = async () => {
    setPendingAction("checkout");
    setActionError(null);
    try {
      const response = await authorizedFetch("/api/billing/checkout-session", {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error(await readErrorMessage(response));
      }
      const payload = (await response.json()) as BillingUrlResponse;
      window.location.assign(payload.url);
    } catch (caughtError) {
      setActionError(
        caughtError instanceof Error
          ? caughtError.message
          : "Unable to start checkout right now.",
      );
    } finally {
      setPendingAction(null);
    }
  };

  const openBillingPortal = async () => {
    setPendingAction("portal");
    setActionError(null);
    try {
      const response = await authorizedFetch("/api/billing/portal-session", {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error(await readErrorMessage(response));
      }
      const payload = (await response.json()) as BillingUrlResponse;
      window.location.assign(payload.url);
    } catch (caughtError) {
      setActionError(
        caughtError instanceof Error
          ? caughtError.message
          : "Unable to open the billing portal right now.",
      );
    } finally {
      setPendingAction(null);
    }
  };

  return (
    <AuthScreen
      eyebrow="Subscription required"
      title="Choose a plan before entering the coach"
      description={detailText}
    >
      <div className="space-y-4">
        {searchParams.get("checkout") === "success" ? (
          <div className="rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm leading-6 text-sky-800 dark:border-sky-400/30 dark:bg-sky-950/40 dark:text-sky-100">
            Payment completed. We're confirming your subscription and will open
            chat as soon as Stripe finishes syncing.
          </div>
        ) : null}

        {actionError ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm leading-6 text-rose-700 dark:border-rose-400/30 dark:bg-rose-950/40 dark:text-rose-100">
            {actionError}
          </div>
        ) : null}

        <button
          type="button"
          onClick={() => {
            void beginCheckout();
          }}
          disabled={pendingAction !== null}
          className="inline-flex w-full items-center justify-center rounded-2xl bg-slate-950 px-5 py-4 text-base font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-white dark:text-slate-950 dark:hover:bg-slate-100"
        >
          {pendingAction === "checkout" ? "Redirecting to Stripe..." : "Subscribe"}
        </button>

        {access?.can_manage_billing ? (
          <button
            type="button"
            onClick={() => {
              void openBillingPortal();
            }}
            disabled={pendingAction !== null}
            className="inline-flex w-full items-center justify-center rounded-2xl border border-slate-300 bg-white px-5 py-4 text-base font-semibold text-slate-900 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100 dark:hover:bg-slate-800"
          >
            {pendingAction === "portal" ? "Opening portal..." : "Manage billing"}
          </button>
        ) : null}
      </div>
    </AuthScreen>
  );
}
