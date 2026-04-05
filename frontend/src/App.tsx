import { Navigate, Route, Routes } from "react-router-dom";
import { AccessProvider } from "./auth/AccessProvider";
import { Auth0ProviderWithNavigate } from "./auth/Auth0ProviderWithNavigate";
import { PaidRoute } from "./auth/PaidRoute";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { Auth0SetupPage, LoginPage } from "./components/LoginPage";
import { ChatKitPanel } from "./components/ChatKitPanel";
import { SubscribePage } from "./components/SubscribePage";
import { AUTH0_IS_CONFIGURED } from "./lib/config";

function ChatPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-slate-100 dark:bg-slate-950">
      <div className="mx-auto w-full max-w-5xl">
        <ChatKitPanel />
      </div>
    </main>
  );
}

function AuthenticatedRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/subscribe"
        element={
          <ProtectedRoute>
            <SubscribePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <PaidRoute>
              <ChatPage />
            </PaidRoute>
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function SetupRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Auth0SetupPage />} />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}

export default function App() {
  if (!AUTH0_IS_CONFIGURED) {
    return <SetupRoutes />;
  }

  return (
    <Auth0ProviderWithNavigate>
      <AccessProvider>
        <AuthenticatedRoutes />
      </AccessProvider>
    </Auth0ProviderWithNavigate>
  );
}
