import { ChatKitPanel } from "./components/ChatKitPanel";

export default function App() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-end bg-slate-100 dark:bg-slate-950">
      <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6">
        <p className="mb-4 text-sm font-medium text-slate-700 dark:text-slate-200">
          Hello, world.
        </p>
        <ChatKitPanel />
      </div>
    </main>
  );
}
