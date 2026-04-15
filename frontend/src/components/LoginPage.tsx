import { AuthScreen } from "./AuthScreen";

export function Auth0SetupPage() {
  return (
    <AuthScreen
      eyebrow="Setup required"
      title="Auth0 is not configured yet"
      description="Add your Auth0 SPA settings before this app can open the login flow."
      variant="minimal"
    >
      <div className="space-y-4 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-4 text-sm leading-7 text-amber-900 dark:border-amber-400/30 dark:bg-amber-950/40 dark:text-amber-100">
        <p>
          Set <code>VITE_AUTH0_DOMAIN</code> and{" "}
          <code>VITE_AUTH0_CLIENT_ID</code> and{" "}
          <code>VITE_AUTH0_AUDIENCE</code> in the app environment.
        </p>
        <p>
          For local development, add <code>http://localhost:3000/</code> as an
          Auth0 callback URL, add <code>http://localhost:3000</code> as an
          allowed web origin, and configure the same Auth0 API audience that
          the frontend uses to call this backend.
        </p>
      </div>
    </AuthScreen>
  );
}
