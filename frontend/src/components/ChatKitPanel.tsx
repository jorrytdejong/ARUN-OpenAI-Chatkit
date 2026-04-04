import {
  startTransition,
  useEffect,
  useState,
} from "react";
import { ChatKit, useChatKit } from "@openai/chatkit-react";
import {
  buildSuggestionsUrl,
  CHATKIT_API_DOMAIN_KEY,
  CHATKIT_API_URL,
} from "../lib/config";

type PromptSuggestion = {
  label: string;
  prompt: string;
};

type PromptSuggestionResponse = {
  hasHistory: boolean;
  suggestions: PromptSuggestion[];
};

let cachedStarterSuggestions: PromptSuggestion[] | null = null;
let starterSuggestionsRequest: Promise<PromptSuggestion[]> | null = null;

const loadStarterSuggestions = async (): Promise<PromptSuggestion[]> => {
  if (cachedStarterSuggestions) {
    return cachedStarterSuggestions;
  }

  if (!starterSuggestionsRequest) {
    starterSuggestionsRequest = fetch(buildSuggestionsUrl(null), {
      credentials: "same-origin",
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Suggestion request failed with status ${response.status}`);
        }

        const payload = (await response.json()) as PromptSuggestionResponse;
        return payload.suggestions;
      })
      .catch((error) => {
        console.error("Failed to load starter suggestions", error);
        return [];
      })
      .then((result) => {
        cachedStarterSuggestions = result;
        return result;
      })
      .finally(() => {
        starterSuggestionsRequest = null;
      });
  }

  return starterSuggestionsRequest;
};

export function ChatKitPanel() {
  const [suggestions, setSuggestions] = useState<PromptSuggestion[]>(
    cachedStarterSuggestions ?? [],
  );
  const [isReady, setIsReady] = useState(cachedStarterSuggestions !== null);

  useEffect(() => {
    let active = true;

    void loadStarterSuggestions().then((result) => {
      if (!active) {
        return;
      }

      startTransition(() => {
        setSuggestions(result);
        setIsReady(true);
      });
    });

    return () => {
      active = false;
    };
  }, []);

  const chatkit = useChatKit({
    api: { url: CHATKIT_API_URL, domainKey: CHATKIT_API_DOMAIN_KEY },
    startScreen: {
      greeting: "Welcome to your Meditative Juice Coach 🍇🧘",
      prompts: suggestions,
    },
    composer: {
      // File uploads stay off in v1 because retrieval uses a pre-indexed ARUN corpus.
      attachments: { enabled: false },
    },
  });

  return (
    <div className="relative flex h-[90vh] w-full min-h-0 flex-col overflow-hidden rounded-2xl bg-white shadow-sm transition-colors dark:bg-slate-900">
      {isReady ? (
        <ChatKit control={chatkit.control} className="block h-full w-full" />
      ) : null}
    </div>
  );
}
