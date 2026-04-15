import { Navigate, Route, Routes } from "react-router-dom";
import { Auth0ProviderWithNavigate } from "./auth/Auth0ProviderWithNavigate";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { Auth0SetupPage } from "./components/LoginPage";
import { ChatKitPanel } from "./components/ChatKitPanel";
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
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <ChatPage />
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
      <Route path="/" element={<Auth0SetupPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  if (!AUTH0_IS_CONFIGURED) {
    return <SetupRoutes />;
  }

  return (
    <Auth0ProviderWithNavigate>
      <AuthenticatedRoutes />
    </Auth0ProviderWithNavigate>
  );
}
