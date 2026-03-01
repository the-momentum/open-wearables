"use client";

import { useChat } from "@ai-sdk/react";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";

const STATUS_MESSAGES = [
  "Searching the docs...",
  "Reading through the pages...",
  "Finding the best answer...",
  "Digging deeper...",
  "Connecting the dots...",
  "Almost there...",
  "Pulling it all together...",
  "Cross-referencing sources...",
  "Polishing the answer...",
];

function ThinkingIndicator() {
  const [index, setIndex] = useState(0);
  const [fade, setFade] = useState(true);

  useEffect(() => {
    const interval = setInterval(() => {
      setFade(false);
      setTimeout(() => {
        setIndex((i) => (i + 1) % STATUS_MESSAGES.length);
        setFade(true);
      }, 300);
    }, 2500);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex items-start gap-3">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[var(--primary)]/10">
        <svg
          className="h-4 w-4 animate-spin text-[var(--primary)]"
          viewBox="0 0 24 24"
          fill="none"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="3"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
      </div>
      <div className="pt-1">
        <p
          className={`text-sm text-[var(--foreground)]/50 transition-opacity duration-300 ${fade ? "opacity-100" : "opacity-0"}`}
        >
          {STATUS_MESSAGES[index]}
        </p>
      </div>
    </div>
  );
}

export default function Chat() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const { messages, input, handleInputChange, handleSubmit, isLoading, error } =
    useChat({ maxSteps: 3 });

  const lastMessage = messages.at(-1);
  const isStreaming = isLoading && lastMessage?.role === "assistant" && lastMessage.content;
  const showThinking = isLoading && !isStreaming;

  // Auto-scroll on new content
  useEffect(() => {
    const el = scrollRef.current;
    if (el) {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }
  }, [messages, isLoading]);

  return (
    <div className="mx-auto flex h-dvh max-w-2xl flex-col">
      <header className="flex items-center gap-3 border-b border-[var(--border)] px-4 py-3">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={2}
          className="h-6 w-6 text-[var(--primary)]"
        >
          <path d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
        </svg>
        <div>
          <h1 className="text-lg font-semibold">Open Wearables Docs</h1>
          <p className="text-xs text-[var(--foreground)]/50">
            Ask anything about the documentation
          </p>
        </div>
      </header>

      <div
        ref={scrollRef}
        className="flex-1 space-y-4 overflow-y-auto px-4 py-6"
      >
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center">
            <div className="space-y-4 text-center">
              <p className="text-lg text-[var(--foreground)]/40">
                Ask a question about Open Wearables
              </p>
              <div className="flex flex-wrap justify-center gap-2">
                {[
                  "How do I get started?",
                  "What providers are supported?",
                  "How does the API work?",
                ].map((q) => (
                  <button
                    key={q}
                    type="button"
                    onClick={() => {
                      handleInputChange({
                        target: { value: q },
                      } as React.ChangeEvent<HTMLInputElement>);
                      setTimeout(() => {
                        const form = document.querySelector("form");
                        form?.requestSubmit();
                      }, 0);
                    }}
                    className="rounded-full border border-[var(--border)] px-3 py-1.5 text-sm transition-colors hover:bg-[var(--muted)]"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {messages
          .filter((m) => m.content)
          .map((m) => (
            <div
              key={m.id}
              className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
            >
              {m.role === "user" ? (
                <div className="max-w-[80%] rounded-2xl bg-[var(--primary)] px-4 py-2.5 text-sm text-[var(--primary-foreground)]">
                  {m.content}
                </div>
              ) : (
                <div className="max-w-full rounded-2xl bg-[var(--muted)] px-5 py-4">
                  <div className="prose prose-neutral dark:prose-invert max-w-none prose-headings:mt-4 prose-headings:mb-2 prose-h2:text-lg prose-h3:text-base prose-p:my-2 prose-ul:my-2 prose-ol:my-2 prose-li:my-0.5 prose-pre:my-3 prose-pre:rounded-lg prose-pre:bg-black/5 dark:prose-pre:bg-white/5 prose-code:rounded prose-code:bg-black/5 prose-code:px-1.5 prose-code:py-0.5 prose-code:text-[0.85em] prose-code:before:content-none prose-code:after:content-none dark:prose-code:bg-white/10 prose-a:text-[var(--primary)] prose-a:no-underline hover:prose-a:underline prose-strong:font-semibold">
                    <ReactMarkdown>{m.content}</ReactMarkdown>
                  </div>
                </div>
              )}
            </div>
          ))}

        {showThinking && <ThinkingIndicator />}

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-600 dark:border-red-900 dark:bg-red-950 dark:text-red-400">
            {error.message}
          </div>
        )}
      </div>

      <form
        onSubmit={handleSubmit}
        className="border-t border-[var(--border)] px-4 py-3"
      >
        <div className="flex gap-2">
          <input
            value={input}
            onChange={handleInputChange}
            placeholder="Ask about Open Wearables..."
            className="flex-1 rounded-xl border border-[var(--border)] bg-[var(--muted)] px-4 py-2.5 text-sm outline-none transition-colors placeholder:text-[var(--foreground)]/30 focus:border-[var(--primary)]"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="rounded-xl bg-[var(--primary)] px-4 py-2.5 text-sm font-medium text-[var(--primary-foreground)] transition-opacity disabled:opacity-40"
          >
            Send
          </button>
        </div>
      </form>
    </div>
  );
}
