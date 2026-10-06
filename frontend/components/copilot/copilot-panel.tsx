"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { useAppContext, type AnalysisContext } from "@/components/shell/app-context";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, chat, COPILOT_STARTER_QUESTIONS } from "@/lib/api";
import { answerContent, contextLabel, MISSING_SAMPLE_ANSWER } from "./copilot-display";

interface Message {
  role: "user" | "assistant";
  content: string;
  citedNodes: string[];
}

// Created on first use in the browser and shared across drawer mounts for this page load.
let pageSessionId: string | undefined;
function getSessionId() {
  pageSessionId ??= crypto.randomUUID();
  return pageSessionId;
}

function Conversation({ context }: { context: AnalysisContext }) {
  const { setHighlight } = useAppContext();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const busy = useRef(false);
  const mounted = useRef(true);
  const bottom = useRef<HTMLDivElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "nearest" });
  }, [messages, loading]);

  async function send(message = input, starterIndex?: number) {
    const content = message.trim();
    if (!content || busy.current) return;
    busy.current = true;
    setLoading(true);
    setInput("");
    setMessages((previous) => [...previous, { role: "user", content, citedNodes: [] }]);
    try {
      const response = await chat({
        session_id: getSessionId(), message: content,
        context_type: context.type, context_id: context.id,
      }, { starterIndex });
      if (mounted.current) setMessages((previous) => [...previous, {
        role: "assistant", content: answerContent(response), citedNodes: response.cited_nodes,
      }]);
    } catch (error) {
      const content = error instanceof ApiError && error.status === 404
        ? MISSING_SAMPLE_ANSWER
        : "Couldn't load the copilot answer. Start the backend or try a starter question in sample mode.";
      if (mounted.current) setMessages((previous) => [...previous, {
        role: "assistant", content, citedNodes: [],
      }]);
    } finally {
      busy.current = false;
      if (mounted.current) {
        setLoading(false);
        textarea.current?.focus();
      }
    }
  }

  return (
    <>
      <div role="log" aria-label="Copilot conversation" aria-live="polite" aria-relevant="additions"
        className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4 text-dense">
        {messages.length === 0 && (
          <div className="space-y-3">
            <p className="text-muted">Ask a question about this analysis.</p>
            <div className="flex flex-wrap gap-2" aria-label="Starter questions">
              {COPILOT_STARTER_QUESTIONS.map((question, index) => (
                <Button key={question} variant="outline" size="sm" className="h-auto whitespace-normal border-line bg-surface text-left text-dense text-azure"
                  onClick={() => void send(question, index)}>
                  {question}
                </Button>
              ))}
            </div>
          </div>
        )}
        {messages.map((message, index) => (
          <div key={index} className={message.role === "user" ? "ml-8 flex justify-end" : "mr-4"}>
            <div className={message.role === "user" ? "max-w-full rounded-md bg-surface-raised px-3 py-2" : "min-w-0 max-w-full"}>
              <span className="sr-only">{message.role === "user" ? "You" : "Copilot"}: </span>
              {message.role === "user" ? (
                <p className="whitespace-pre-wrap break-words">{message.content}</p>
              ) : (
                <>
                  <div className="break-words [overflow-wrap:anywhere] [&_p]:my-2 [&_p:first-child]:mt-0 [&_p:last-child]:mb-0 [&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-4 [&_ol]:my-2 [&_ol]:list-decimal [&_ol]:pl-4 [&_li]:my-1 [&_strong]:font-semibold [&_h1]:my-2 [&_h1]:text-body [&_h2]:my-2 [&_h2]:text-body [&_h3]:my-2 [&_h3]:text-body [&_code]:rounded-sm [&_code]:bg-surface-raised [&_code]:px-1 [&_code]:font-sans [&_pre]:overflow-x-auto [&_pre]:whitespace-pre-wrap [&_blockquote]:border-l-2 [&_blockquote]:border-line [&_blockquote]:pl-3 [&_a]:text-azure [&_a]:underline">
                    <ReactMarkdown skipHtml components={{ img: () => null }}>{message.content}</ReactMarkdown>
                  </div>
                  {message.citedNodes.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1.5" aria-label="Cited components">
                      {message.citedNodes.slice(0, 8).map((id) => (
                        <Button key={id} variant="outline" size="xs" className="border-line bg-surface text-meta text-azure"
                          aria-label={`Highlight ${id} in the graph`} onClick={() => setHighlight([id])}>
                          {id}
                        </Button>
                      ))}
                      {message.citedNodes.length > 8 && <span className="self-center text-meta text-muted">+{message.citedNodes.length - 8} more</span>}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        ))}
        {loading && <p role="status" className="text-muted">Thinking…</p>}
        <div ref={bottom} />
      </div>
      <form className="space-y-2 border-t border-line p-4" onSubmit={(event) => {
        event.preventDefault();
        void send();
      }}>
        <label htmlFor="copilot-question" className="sr-only">Ask about this analysis</label>
        <Textarea id="copilot-question" ref={textarea} value={input} aria-describedby="copilot-input-help"
          placeholder="Ask about this analysis…" aria-disabled={loading}
          className="max-h-40 min-h-20 resize-none border-line bg-canvas text-body md:text-body"
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              void send();
            }
          }} />
        <div className="flex items-center justify-between gap-3">
          <p id="copilot-input-help" className="text-meta text-muted">Enter to send · Shift+Enter for a new line</p>
          <Button type="submit" disabled={loading || !input.trim()}>Ask</Button>
        </div>
      </form>
    </>
  );
}

export function CopilotPanel() {
  const { currentContext, currentAnalysis } = useAppContext();
  return (
    <section className="flex min-h-0 flex-1 flex-col" aria-label="Analysis copilot">
      <header className="border-b border-line p-4 pr-12">
        <h2>Copilot</h2>
        <p className="mt-1 text-dense text-muted">
          {currentContext ? `Asking about ${contextLabel(currentContext, currentAnalysis)}` : "Ask about the current analysis."}
        </p>
      </header>
      {currentContext ? (
        <Conversation key={`${currentContext.type}:${currentContext.id}`} context={currentContext} />
      ) : (
        <p className="p-4 text-body text-muted">Analyze a story or sprint first, then ask about it here.</p>
      )}
    </section>
  );
}
