import { useAuth0 } from "@auth0/auth0-react";
import {
  useCallback,
  type ReactNode,
  useEffect,
  useState,
} from "react";
import { AUTH0_AUDIENCE } from "../lib/config";
import { AccessContext, type AccessSnapshot } from "./access-context";

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string };
    if (typeof payload.detail === "string" && payload.detail.length > 0) {
      return payload.detail;
    }
  } catch {
    // Fall back to a generic message below.
  }
  return `Request failed with status ${response.status}`;
}

type AccessProviderProps = {
  children: ReactNode;
};

export function AccessProvider({ children }: AccessProviderProps) {
  const { getAccessTokenSilently, isAuthenticated, isLoading: isAuthLoading } =
    useAuth0();
  const [access, setAccess] = useState<AccessSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const authorizedFetch: typeof fetch = useCallback(
    async (input, init) => {
      const token = await getAccessTokenSilently({
        authorizationParams: { audience: AUTH0_AUDIENCE },
      });
      const headers = new Headers(init?.headers);
      headers.set("Authorization", `Bearer ${token}`);
      return fetch(input, { ...init, headers });
    },
    [getAccessTokenSilently],
  );

  const refreshAccess = useCallback(async (): Promise<AccessSnapshot | null> => {
    if (!isAuthenticated) {
      setAccess(null);
      setError(null);
      return null;
    }

    setIsLoading(true);
    try {
      const response = await authorizedFetch("/api/me/access");
      if (!response.ok) {
        throw new Error(await readErrorMessage(response));
      }

      const payload = (await response.json()) as AccessSnapshot;
      setAccess(payload);
      setError(null);
      return payload;
    } catch (caughtError) {
      const message =
        caughtError instanceof Error
          ? caughtError.message
          : "Unable to load your subscription access.";
      setError(message);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [authorizedFetch, isAuthenticated]);

  useEffect(() => {
    if (isAuthLoading) {
      return;
    }
    if (!isAuthenticated) {
      setAccess(null);
      setError(null);
      setIsLoading(false);
      return;
    }

    void refreshAccess();
  }, [isAuthenticated, isAuthLoading, refreshAccess]);

  return (
    <AccessContext.Provider
      value={{
        access,
        error,
        isLoading: isLoading || isAuthLoading,
        authorizedFetch,
        refreshAccess,
      }}
    >
      {children}
    </AccessContext.Provider>
  );
}
