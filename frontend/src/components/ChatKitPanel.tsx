import { ChatKit, useChatKit } from "@openai/chatkit-react";
import { useAuth0 } from "@auth0/auth0-react";
import type { Entity } from "@openai/chatkit";
import { useCallback } from "react";
import {
  AUTH0_AUDIENCE,
  CHATKIT_API_DOMAIN_KEY,
  CHATKIT_API_URL,
} from "../lib/config";

function buildSourcePreview(entity: Entity) {
  const snippet = entity.data?.snippet?.trim();
  if (!snippet) {
    return null;
  }

  return {
    type: "Basic" as const,
    children: [
      {
        type: "Col" as const,
        gap: 1,
        padding: 2,
        children: [
          {
            type: "Title" as const,
            value: entity.title,
            size: "sm" as const,
          },
          {
            type: "Caption" as const,
            value: "Retrieved source excerpt",
            size: "sm" as const,
            color: "secondary",
          },
          {
            type: "Text" as const,
            value: snippet,
            size: "sm" as const,
          },
        ],
      },
    ],
  };
}

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
    entities: {
      onRequestPreview: async (entity) => ({
        preview: buildSourcePreview(entity),
      }),
    },
  });

  return (
    <div className="relative flex h-[90vh] w-full flex-col overflow-hidden rounded-2xl bg-white pb-8 shadow-sm transition-colors dark:bg-slate-900">
      <ChatKit control={chatkit.control} className="block h-full w-full" />
    </div>
  );
}
