import { ChatKit, useChatKit } from "@openai/chatkit-react";
import { useAuth0 } from "@auth0/auth0-react";
import { useCallback } from "react";
import {
  AUTH0_AUDIENCE,
  CHATKIT_API_DOMAIN_KEY,
  CHATKIT_API_URL,
} from "../lib/config";

export function ChatKitPanel() {
  const { getAccessTokenSilently } = useAuth0();
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

  const chatkit = useChatKit({
    api: {
      url: CHATKIT_API_URL,
      domainKey: CHATKIT_API_DOMAIN_KEY,
      fetch: authorizedFetch,
    },
    history: {
      enabled: true,
      showDelete: true,
      showRename: true,
    },
    startScreen: {
      greeting: "Welcome to ARUN Meditative Juice Guru 🍇🧘",
    },
    composer: {
      // File uploads stay off in v1 because retrieval uses a pre-indexed ARUN corpus.
      attachments: { enabled: false },
    },
  });

  return (
    <div className="relative flex h-[90vh] w-full flex-col overflow-hidden rounded-2xl bg-white pb-8 shadow-sm transition-colors dark:bg-slate-900">
      <ChatKit control={chatkit.control} className="block h-full w-full" />
    </div>
  );
}
