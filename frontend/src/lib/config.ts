const readEnvString = (value: unknown): string | undefined =>
  typeof value === "string" && value.trim().length > 0
    ? value.trim()
    : undefined;

const runtimeConfig =
  typeof window !== "undefined" ? window.__CHATKIT_CONFIG__ : undefined;
const hasRuntimeConfig = runtimeConfig !== undefined;

export const CHATKIT_API_URL =
  (hasRuntimeConfig ? runtimeConfig?.apiUrl || "/chatkit" : undefined) ??
  readEnvString(import.meta.env.VITE_CHATKIT_API_URL) ??
  "/chatkit";

/**
 * ChatKit requires a domain key at runtime. Use the local fallback while
 * developing, and register a production domain key for deployment:
 * https://platform.openai.com/settings/organization/security/domain-allowlist
 */
export const CHATKIT_API_DOMAIN_KEY =
  (hasRuntimeConfig ? runtimeConfig?.domainKey || "" : undefined) ??
  readEnvString(import.meta.env.VITE_CHATKIT_API_DOMAIN_KEY) ??
  "domain_pk_localhost_dev";

export const AUTH0_DOMAIN =
  (hasRuntimeConfig ? runtimeConfig?.auth0Domain || "" : undefined) ??
  readEnvString(import.meta.env.VITE_AUTH0_DOMAIN) ??
  "";

export const AUTH0_CLIENT_ID =
  (hasRuntimeConfig ? runtimeConfig?.auth0ClientId || "" : undefined) ??
  readEnvString(import.meta.env.VITE_AUTH0_CLIENT_ID) ??
  "";

export const AUTH0_AUDIENCE =
  (hasRuntimeConfig ? runtimeConfig?.auth0Audience || "" : undefined) ??
  readEnvString(import.meta.env.VITE_AUTH0_AUDIENCE) ??
  "";

export const AUTH0_IS_CONFIGURED =
  AUTH0_DOMAIN.length > 0 &&
  AUTH0_CLIENT_ID.length > 0 &&
  AUTH0_AUDIENCE.length > 0;

const CHATKIT_API_BASE = CHATKIT_API_URL.replace(/\/$/, "");

export const buildSuggestionsUrl = (threadId?: string | null): string =>
  threadId
    ? `${CHATKIT_API_BASE}/threads/${encodeURIComponent(threadId)}/suggestions`
    : `${CHATKIT_API_BASE}/suggestions`;
