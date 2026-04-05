import { useAuth0 } from "@auth0/auth0-react";
import { Navigate, useLocation } from "react-router-dom";
import { AuthScreen } from "./AuthScreen";

type LoginLocationState = {
  returnTo?: string;
};

const readReturnTo = (state: unknown): string => {
  if (!state || typeof state !== "object") {
    return "/";
  }

  const { returnTo } = state as LoginLocationState;
  if (typeof returnTo !== "string" || !returnTo.startsWith("/")) {
    return "/";
  }

  return returnTo;
};

export function LoginPage() {
  const { error, isAuthenticated, isLoading, loginWithRedirect } = useAuth0();
  const location = useLocation();
  const returnTo = readReturnTo(location.state);

  if (isLoading) {
    return (
      <AuthScreen
        eyebrow="Preparing sign-in"
        title="Loading your secure entry"
        description="One moment while we get the login flow ready."
      />
    );
  }

  if (isAuthenticated) {
    return <Navigate to={returnTo} replace />;
  }

  return (
    <AuthScreen
      eyebrow="Protected access"
      title="Sign in before entering the chat"
      description="Use your Auth0 account to unlock the Meditative Juice Coach. Once you're in, the chat page stays exactly as it is."
    >
      {error ? (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm leading-6 text-rose-700 dark:border-rose-400/30 dark:bg-rose-950/40 dark:text-rose-100">
          {error.message}
        </div>
      ) : null}

      <button
        type="button"
        onClick={() => {
          void loginWithRedirect({ appState: { returnTo } });
        }}
        className="inline-flex w-full items-center justify-center rounded-2xl bg-slate-950 px-5 py-4 text-base font-semibold text-white transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2 focus:ring-offset-white dark:bg-white dark:text-slate-950 dark:hover:bg-slate-100 dark:focus:ring-slate-500 dark:focus:ring-offset-slate-950"
      >
        Continue with Auth0
      </button>
    </AuthScreen>
  );
}

export function Auth0SetupPage() {
  return (
    <AuthScreen
      eyebrow="Setup required"
      title="Auth0 is not configured yet"
      description="Add your Auth0 SPA settings before this app can open the login flow."
    >
      <div className="space-y-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm leading-7 text-amber-900 dark:border-amber-400/30 dark:bg-amber-950/40 dark:text-amber-100">
        <p>
          Set <code>VITE_AUTH0_DOMAIN</code> and{" "}
          <code>VITE_AUTH0_CLIENT_ID</code> and{" "}
          <code>VITE_AUTH0_AUDIENCE</code> in the app environment.
        </p>
        <p>
          For local development, add <code>http://localhost:3000/login</code>{" "}
          as an Auth0 callback URL and <code>http://localhost:3000</code> as an
          allowed web origin, and configure the same Auth0 API audience that
          the frontend uses to call this backend.
        </p>
      </div>
    </AuthScreen>
  );
}
