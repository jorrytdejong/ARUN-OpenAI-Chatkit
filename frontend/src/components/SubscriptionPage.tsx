import { Link } from "react-router-dom";
import { useState } from "react";
import { AuthScreen } from "./AuthScreen";
import { useAccess } from "../auth/access-context";

type CancelAtPeriodEndResponse = {
  stripe_subscription_id: string;
  stripe_subscription_status: string | null;
  cancel_at_period_end: boolean;
  current_period_end: string | null;
  cancellation_requested_at: string | null;
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

function formatDate(value: string | null): string | null {
  if (!value) {
    return null;
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(parsed);
}

function describeStatus(status: string | null) {
  if (status === "active") {
    return "Active";
  }
  if (status === "trialing") {
    return "Trialing";
  }
  if (status === "past_due") {
    return "Past due";
  }
  if (status === "canceled") {
    return "Canceled";
  }
  return "Not started";
}

export function SubscriptionPage() {
  const { access, authorizedFetch, error, isLoading, refreshAccess } = useAccess();
  const [isConfirmingCancel, setIsConfirmingCancel] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [scheduledPeriodEnd, setScheduledPeriodEnd] = useState<string | null>(null);

  if (isLoading) {
    return (
      <AuthScreen
        eyebrow="Loading subscription"
        title="Checking your plan details"
        description="One moment while we load your subscription overview."
        variant="minimal"
      />
    );
  }

  if (error) {
    return (
      <AuthScreen
        eyebrow="Subscription unavailable"
        title="We couldn't load your subscription details"
        description={error}
        variant="minimal"
      />
    );
  }

  const renewalText = access?.current_period_end
    ? (formatDate(access.current_period_end) ?? "Renewal date unavailable")
    : "Stripe will confirm your next renewal date after checkout.";
  const isAlreadyEnding = Boolean(access?.cancel_at_period_end);
  const isEndingScheduled = isAlreadyEnding || scheduledPeriodEnd !== null;
  const endDateForDisplay =
    scheduledPeriodEnd ?? access?.current_period_end ?? null;
  const endDateText = formatDate(endDateForDisplay);
  const statusText = isEndingScheduled
    ? endDateText
      ? `Ending on ${endDateText}`
      : "Ending at period end"
    : describeStatus(access?.stripe_subscription_status ?? null);
  const renewalStatusText = isEndingScheduled
    ? "Off (no further renewal)"
    : renewalText;

  const endSubscriptionAtPeriodEnd = async () => {
    if (!access?.stripe_subscription_id) {
      setActionError("No active subscription found for this account.");
      return;
    }

    setActionError(null);
    setSuccessMessage(null);
    setIsCancelling(true);
    try {
      const response = await authorizedFetch(
        `/api/billing/subscriptions/${access.stripe_subscription_id}/cancel-at-period-end`,
        { method: "POST" },
      );
      if (!response.ok) {
        throw new Error(await readErrorMessage(response));
      }

      const payload = (await response.json()) as CancelAtPeriodEndResponse;
      const refreshedSnapshot = await refreshAccess();
      const resolvedPeriodEnd =
        payload.current_period_end ??
        refreshedSnapshot?.current_period_end ??
        access?.current_period_end ??
        null;
      const resolvedEndDate = formatDate(resolvedPeriodEnd);
      setScheduledPeriodEnd(resolvedPeriodEnd);
      if (resolvedEndDate) {
        setSuccessMessage(
          `Subscription will end on ${resolvedEndDate}. Renewal is off, and access remains active until then.`,
        );
      } else {
        setSuccessMessage(
          "Subscription is set to end at period end. Renewal is off, and access remains active until then.",
        );
      }
      setIsConfirmingCancel(false);
    } catch (caughtError) {
      setActionError(
        caughtError instanceof Error
          ? caughtError.message
          : "Unable to schedule cancellation right now.",
      );
    } finally {
      setIsCancelling(false);
    }
  };

  return (
    <AuthScreen
      eyebrow="Subscription"
      title="Your subscription overview"
      description="Review the current plan, renewal timing, and what happens if you choose to cancel."
      variant="minimal"
    >
      <div className="space-y-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-slate-900 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100">
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-4">
              <span className="text-slate-500 dark:text-slate-400">Plan</span>
              <span className="font-semibold">Monthly coach access</span>
            </div>
            <div className="flex items-center justify-between gap-4">
              <span className="text-slate-500 dark:text-slate-400">Status</span>
              <span className="font-semibold">{statusText}</span>
            </div>
            <div className="flex items-center justify-between gap-4">
              <span className="text-slate-500 dark:text-slate-400">Renewal</span>
              <span className="text-right font-semibold">{renewalStatusText}</span>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900 dark:border-amber-400/30 dark:bg-amber-950/30 dark:text-amber-100">
          Cancel at period end means the subscription stays active until the
          current paid billing period finishes. You keep access during that
          period, and renewal stops after it ends.
        </div>

        {successMessage ? (
          <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm leading-6 text-emerald-800 dark:border-emerald-400/30 dark:bg-emerald-950/30 dark:text-emerald-100">
            {successMessage}
          </div>
        ) : null}

        {actionError ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm leading-6 text-rose-700 dark:border-rose-400/30 dark:bg-rose-950/40 dark:text-rose-100">
            {actionError}
          </div>
        ) : null}

        {isConfirmingCancel && !isEndingScheduled ? (
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm leading-6 text-slate-800 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200">
            <p className="font-semibold">Confirm end at period end</p>
            <p className="mt-1">
              {endDateText
                ? `Your subscription remains active through ${endDateText}.`
                : "Your subscription remains active through the end of your current paid period."}{" "}
              {endDateText
                ? "You will not be charged again after that date."
                : "You will not be charged again after period end."}
            </p>
            <div className="mt-3 flex flex-col gap-2 sm:flex-row">
              <button
                type="button"
                onClick={() => {
                  void endSubscriptionAtPeriodEnd();
                }}
                disabled={isCancelling}
                className="inline-flex items-center justify-center rounded-2xl bg-slate-950 px-4 py-2 text-sm font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-60 dark:bg-white dark:text-slate-950"
              >
                {isCancelling ? "Scheduling..." : "Confirm end at period end"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setIsConfirmingCancel(false);
                  setActionError(null);
                }}
                disabled={isCancelling}
                className="inline-flex items-center justify-center rounded-2xl border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-900 transition disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
              >
                Keep subscription
              </button>
            </div>
          </div>
        ) : null}

        <div className="flex flex-col gap-3 sm:flex-row">
          <button
            type="button"
            className="inline-flex items-center justify-center rounded-2xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition dark:bg-white dark:text-slate-950"
          >
            Manage subscription
          </button>
          <button
            type="button"
            onClick={() => {
              setIsConfirmingCancel(true);
              setActionError(null);
              setSuccessMessage(null);
            }}
            disabled={isEndingScheduled || isCancelling}
            className="inline-flex items-center justify-center rounded-2xl border border-slate-300 bg-white px-5 py-3 text-sm font-semibold text-slate-900 transition dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
          >
            {isEndingScheduled
              ? endDateText
                ? `Ending on ${endDateText}`
                : "Ending at period end"
              : "End subscription"}
          </button>
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-2xl border border-transparent px-5 py-3 text-sm font-semibold text-slate-600 transition hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
          >
            Back to chat
          </Link>
        </div>
      </div>
    </AuthScreen>
  );
}
