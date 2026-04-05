import type { ReactNode } from "react";

type AuthScreenProps = {
  eyebrow: string;
  title: string;
  description: string;
  children?: ReactNode;
};

export function AuthScreen({
  eyebrow,
  title,
  description,
  children,
}: AuthScreenProps) {
  return (
    <main className="relative min-h-screen overflow-hidden bg-[radial-gradient(circle_at_top,_rgba(255,237,213,0.95),_rgba(255,255,255,1)_38%,_rgba(224,242,254,0.9)_100%)] text-slate-950 dark:bg-[radial-gradient(circle_at_top,_rgba(67,20,7,0.9),_rgba(2,6,23,1)_42%,_rgba(12,74,110,0.72)_100%)] dark:text-slate-50">
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute -left-20 top-16 h-64 w-64 rounded-full bg-orange-300/35 blur-3xl dark:bg-orange-500/20" />
        <div className="absolute right-0 top-1/3 h-72 w-72 rounded-full bg-emerald-200/55 blur-3xl dark:bg-emerald-400/15" />
        <div className="absolute bottom-8 left-1/3 h-48 w-48 rounded-full bg-sky-200/55 blur-3xl dark:bg-sky-400/15" />
      </div>

      <div className="relative mx-auto flex min-h-screen max-w-6xl items-center px-6 py-12">
        <div className="grid w-full gap-8 lg:grid-cols-[1.15fr_0.85fr] lg:items-center">
          <section className="space-y-6">
            <span className="inline-flex rounded-full border border-orange-300/70 bg-white/70 px-4 py-1 text-sm font-medium tracking-[0.18em] text-orange-700 uppercase shadow-sm backdrop-blur dark:border-orange-300/20 dark:bg-slate-900/40 dark:text-orange-200">
              ARUN Juice Guide
            </span>
            <div className="space-y-4">
              <p className="text-sm font-semibold tracking-[0.24em] text-slate-500 uppercase dark:text-slate-300">
                {eyebrow}
              </p>
              <h1 className="max-w-2xl text-4xl font-semibold tracking-tight text-balance sm:text-5xl">
                {title}
              </h1>
              <p className="max-w-2xl text-lg leading-8 text-slate-600 dark:text-slate-300">
                {description}
              </p>
            </div>
          </section>

          <section className="rounded-[2rem] border border-white/70 bg-white/85 p-8 shadow-[0_24px_80px_rgba(15,23,42,0.12)] backdrop-blur dark:border-slate-800/80 dark:bg-slate-950/70 dark:shadow-[0_24px_90px_rgba(2,6,23,0.45)] sm:p-10">
            <div className="space-y-6">
              <div className="space-y-2">
                <p className="text-sm font-medium tracking-[0.18em] text-emerald-700 uppercase dark:text-emerald-300">
                  Secure Access
                </p>
                <h2 className="text-2xl font-semibold tracking-tight">
                  Sign in before opening the coach
                </h2>
              </div>

              <p className="text-sm leading-7 text-slate-600 dark:text-slate-300">
                Access to the chat stays behind Auth0 Universal Login so the
                conversation experience can stay focused once you enter.
              </p>

              {children}
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
