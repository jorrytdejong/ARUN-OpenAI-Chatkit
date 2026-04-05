/// <reference types="vite/client" />

declare global {
  interface Window {
    __CHATKIT_CONFIG__?: {
      apiUrl?: string;
      domainKey?: string;
      auth0Domain?: string;
      auth0ClientId?: string;
      auth0Audience?: string;
    };
  }

  interface ImportMetaEnv {
    readonly VITE_CHATKIT_API_URL?: string;
    readonly VITE_CHATKIT_API_DOMAIN_KEY?: string;
    readonly VITE_AUTH0_DOMAIN?: string;
    readonly VITE_AUTH0_CLIENT_ID?: string;
    readonly VITE_AUTH0_AUDIENCE?: string;
  }

  interface ImportMeta {
    readonly env: ImportMetaEnv;
  }
}

export {};
