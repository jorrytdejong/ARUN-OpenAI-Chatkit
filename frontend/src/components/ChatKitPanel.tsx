import { ChatKit, useChatKit } from "@openai/chatkit-react";
import {
  CHATKIT_API_DOMAIN_KEY,
  CHATKIT_API_URL,
} from "../lib/config";
import { useAccess } from "../auth/access-context";

export function ChatKitPanel() {
  const { authorizedFetch } = useAccess();
  const chatkit = useChatKit({
    api: {
      url: CHATKIT_API_URL,
      domainKey: CHATKIT_API_DOMAIN_KEY,
      fetch: authorizedFetch,
    },
    startScreen: {
      greeting: "Welcome to ARUN Meditative Juice Coach 🍇🧘",
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
