import { ChevronDown, ChevronUp, History, MessageSquare, Plus, Send, Trash2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { Component, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";

import { chatApi } from "../api/client.js";
import logoUrl from "../assets/kb-chat-logo.png";
import { SkeletonBlock } from "../components/Skeleton.jsx";
import { StatusChip } from "../components/StatusChip.jsx";
import { formatDate } from "../utils/format.js";

const SESSION_PAGE_SIZE = 20;
const MESSAGE_PAGE_SIZE = 20;

function mergeById(items) {
  const seen = new Set();
  return items.filter((item) => {
    if (!item?.id || seen.has(item.id)) return false;
    seen.add(item.id);
    return true;
  });
}

export function Chat() {
  const [messages, setMessages] = useState([]);
  const [messagePage, setMessagePage] = useState(1);
  const [messageTotal, setMessageTotal] = useState(0);
  const [question, setQuestion] = useState("");
  const [sessions, setSessions] = useState([]);
  const [sessionPage, setSessionPage] = useState(1);
  const [sessionsTotal, setSessionsTotal] = useState(0);
  const [sessionId, setSessionId] = useState("");
  const [sessionTitle, setSessionTitle] = useState("");
  const [sources, setSources] = useState([]);
  const [modelUsed, setModelUsed] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [loadingMoreSessions, setLoadingMoreSessions] = useState(false);
  const [loadingSession, setLoadingSession] = useState(false);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const [feedback, setFeedback] = useState("");
  const messagesPanelRef = useRef(null);
  const pendingScrollRef = useRef(null);

  const loadSessions = useCallback(async ({ page = 1, append = false } = {}) => {
    if (append) {
      setLoadingMoreSessions(true);
    } else {
      setLoadingSessions(true);
    }
    try {
      const data = await chatApi.sessions({ page, page_size: SESSION_PAGE_SIZE });
      const items = data.items || [];
      setSessions((current) => (append ? mergeById([...current, ...items]) : items));
      setSessionsTotal(data.total || items.length);
      setSessionPage(page);
    } catch (error) {
      setFeedback(error.message);
    } finally {
      if (append) {
        setLoadingMoreSessions(false);
      } else {
        setLoadingSessions(false);
      }
    }
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  useLayoutEffect(() => {
    const container = messagesPanelRef.current;
    const pendingScroll = pendingScrollRef.current;
    if (!container || !pendingScroll) return;

    if (pendingScroll === "bottom") {
      container.scrollTop = container.scrollHeight;
    } else if (pendingScroll.type === "preserve") {
      container.scrollTop = pendingScroll.scrollTop + (container.scrollHeight - pendingScroll.scrollHeight);
    }
    pendingScrollRef.current = null;
  }, [messages]);

  async function openSession(nextSessionId) {
    setLoadingSession(true);
    setFeedback("");
    setMessages([]);
    setMessagePage(1);
    setMessageTotal(0);
    try {
      const session = await chatApi.getSession(nextSessionId, {
        page: 1,
        page_size: MESSAGE_PAGE_SIZE,
      });
      setSessionId(session.id);
      setSessionTitle(session.title || "Saved chat");
      pendingScrollRef.current = "bottom";
      setMessages(session.messages || []);
      setMessagePage(session.messages_page || 1);
      setMessageTotal(session.messages_total ?? (session.messages || []).length);
      setSources([]);
      setModelUsed("");
    } catch (error) {
      setFeedback(error.message);
    } finally {
      setLoadingSession(false);
    }
  }

  async function loadOlderMessages() {
    if (!sessionId || loadingOlder || messages.length >= messageTotal) return;

    const nextPage = messagePage + 1;
    const container = messagesPanelRef.current;
    if (container) {
      pendingScrollRef.current = {
        type: "preserve",
        scrollHeight: container.scrollHeight,
        scrollTop: container.scrollTop,
      };
    }
    setLoadingOlder(true);
    setFeedback("");

    try {
      const session = await chatApi.getSession(sessionId, {
        page: nextPage,
        page_size: MESSAGE_PAGE_SIZE,
      });
      setMessages((current) => mergeById([...(session.messages || []), ...current]));
      setMessagePage(session.messages_page || nextPage);
      setMessageTotal(session.messages_total ?? messageTotal);
    } catch (error) {
      setFeedback(error.message);
    } finally {
      setLoadingOlder(false);
    }
  }

  async function sendQuestion(event) {
    event.preventDefault();
    if (!question.trim() || loading) return;

    const content = question.trim();
    const optimisticMessage = {
      id: `local-${Date.now()}`,
      role: "user",
      content,
      created_at: new Date().toISOString(),
    };
    pendingScrollRef.current = "bottom";
    setMessages((current) => [...current, optimisticMessage]);
    setMessageTotal((current) => current + 1);
    setQuestion("");
    setLoading(true);
    setFeedback("");

    try {
      const response = await chatApi.ask({
        question: content,
        ...(sessionId ? { session_id: sessionId } : {}),
        ...(!sessionId ? { title: content.slice(0, 80) } : {}),
      });
      setSessionId(response.session_id);
      setSessionTitle((current) => current || content.slice(0, 80));
      setSources(response.sources || []);
      setModelUsed(response.model_used || "");
      setMessagePage(1);
      setMessageTotal((current) => current + 1);
      pendingScrollRef.current = "bottom";
      setMessages((current) => [
        ...current.map((message) => (
          message.id === optimisticMessage.id
            ? { ...message, id: response.user_message_id }
            : message
        )),
        {
          id: response.assistant_message_id,
          role: "assistant",
          content: response.answer || "No answer returned.",
          created_at: new Date().toISOString(),
        },
      ]);
      await loadSessions();
    } catch (error) {
      setFeedback(error.message);
      setMessageTotal((current) => Math.max(0, current - 1));
      setMessages((current) => current.filter((message) => message.id !== optimisticMessage.id));
    } finally {
      setLoading(false);
    }
  }

  function startNewChat() {
    setSessionId("");
    setSessionTitle("");
    setSources([]);
    setModelUsed("");
    setMessages([]);
    setMessagePage(1);
    setMessageTotal(0);
    setFeedback("");
  }

  async function deleteCurrentSession() {
    if (!sessionId || !window.confirm("Delete this chat session?")) return;
    try {
      await chatApi.deleteSession(sessionId);
      startNewChat();
      await loadSessions();
      setFeedback("Chat session deleted.");
    } catch (error) {
      setFeedback(error.message);
    }
  }

  const hasMoreSessions = sessions.length < sessionsTotal;
  const hasOlderMessages = Boolean(sessionId) && messages.length < messageTotal;

  return (
    <div className="grid min-h-0 grid-cols-[280px_minmax(0,1fr)_320px] items-start gap-5 max-[1280px]:grid-cols-1">
      <aside className="rounded-lg border border-med-border bg-white p-4 shadow-soft">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-black text-med-text">Chat history</h2>
          <button className="icon-button" type="button" aria-label="New chat" onClick={startNewChat}>
            <Plus size={18} />
          </button>
        </div>
        <div className="grid max-h-[340px] gap-2 overflow-auto pr-1">
          {loadingSessions && Array.from({ length: 4 }).map((_, index) => (
            <div className="rounded-lg border border-med-border bg-med-bg px-3 py-3" key={`session-skeleton-${index}`}>
              <SkeletonBlock className="h-4 w-40" />
              <SkeletonBlock className="mt-2 h-3 w-24" />
            </div>
          ))}
          {!loadingSessions && sessions.length === 0 && (
            <p className="rounded-lg border border-med-border bg-med-bg px-3 py-3 text-sm text-med-muted">No saved sessions yet.</p>
          )}
          {!loadingSessions && sessions.map((session) => (
            <button
              className={`rounded-lg border px-3 py-3 text-left text-sm font-bold hover:border-med-primary hover:bg-white ${session.id === sessionId ? "border-med-primary bg-teal-50 text-med-primary" : "border-med-border bg-med-bg text-med-text"}`}
              key={session.id}
              type="button"
              onClick={() => openSession(session.id)}
            >
              <span className="flex items-center gap-2"><History size={15} /> {session.title || "Untitled session"}</span>
              <span className="mt-1 block text-xs font-semibold text-med-muted">{formatDate(session.updated_at)}</span>
            </button>
          ))}
          {!loadingSessions && hasMoreSessions && (
            <button
              className="secondary-button w-full"
              disabled={loadingMoreSessions}
              type="button"
              onClick={() => loadSessions({ page: sessionPage + 1, append: true })}
            >
              <ChevronDown size={16} /> {loadingMoreSessions ? "Loading..." : "More chats"}
            </button>
          )}
        </div>
      </aside>

      <section className="grid h-[calc(100vh-190px)] min-h-[520px] min-w-0 grid-rows-[auto_minmax(0,1fr)_auto] overflow-hidden rounded-lg border border-med-border bg-white shadow-soft max-sm:h-[calc(100vh-150px)] max-sm:min-h-[460px]">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-med-border px-6 py-5">
          <div>
            <h1 className="text-xl font-black text-med-text">{sessionTitle || "New chat"}</h1>
            <p className="text-sm text-med-muted">Ask against documents your account can access.</p>
          </div>
          <div className="flex gap-2">
            <button className="icon-button" type="button" aria-label="New chat" onClick={startNewChat}><Plus size={18} /></button>
            <button className="icon-button text-med-error" disabled={!sessionId} type="button" aria-label="Delete chat" onClick={deleteCurrentSession}><Trash2 size={18} /></button>
          </div>
        </header>

        <div className="min-h-0 overflow-auto px-7 py-6" ref={messagesPanelRef}>
          {loadingSession && <p className="rounded-lg border border-sky-100 bg-sky-50 p-3 text-sm font-semibold text-sky-700">Loading session...</p>}
          {!loadingSession && hasOlderMessages && (
            <div className="mb-5 flex justify-center">
              <button className="secondary-button" disabled={loadingOlder} type="button" onClick={loadOlderMessages}>
                <ChevronUp size={16} /> {loadingOlder ? "Loading..." : "Older messages"}
              </button>
            </div>
          )}
          {!loadingSession && messages.length === 0 && (
            <div className="grid min-h-[360px] place-items-center text-center">
              <div className="max-w-md">
                <span className="mx-auto grid h-14 w-14 place-items-center rounded-lg border-2 border-med-primary text-med-primary"><MessageSquare size={24} /></span>
                <h2 className="mt-5 text-2xl font-black text-med-text">Start with a backend question.</h2>
                <p className="mt-2 text-med-muted">Answers return with source names from the knowledge base when context is found.</p>
              </div>
            </div>
          )}
          <div className="grid gap-6">
            {messages.map((message) => {
              const isUserMessage = message.role === "user";
              return (
                <article className={`flex gap-4 ${isUserMessage ? "justify-end" : "justify-start"}`} key={message.id || `${message.role}-${message.created_at}`}>
                  {!isUserMessage && (
                    <img
                      src={logoUrl}
                      alt=""
                      aria-hidden="true"
                      className="h-11 w-11 shrink-0 rounded-lg border border-med-border bg-white object-contain p-1.5"
                    />
                  )}
                  <div className={`max-w-3xl rounded-lg border border-med-border p-4 break-words ${isUserMessage ? "bg-med-bg" : "bg-white"}`}>
                    <p className="mb-2 text-sm font-black text-med-text">{isUserMessage ? "You" : "KB Chat Bot Dev AI"}</p>
                    {!isUserMessage ? (
                      <MessageRenderBoundary fallback={message.content}>
                        <MarkdownMessage content={message.content} />
                      </MessageRenderBoundary>
                    ) : (
                      <p className="whitespace-pre-wrap leading-7">{message.content}</p>
                    )}
                  </div>
                </article>
              );
            })}
            {loading && <p className="rounded-lg border border-sky-100 bg-sky-50 p-3 text-sm font-semibold text-sky-700">Generating answer...</p>}
          </div>
        </div>

        <form className="m-5 grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-lg border border-med-border bg-white p-3 shadow-soft max-sm:grid-cols-1" onSubmit={sendQuestion}>
          <input className="input" value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ask a question..." />
          <button className="primary-button" disabled={loading || !question.trim()} type="submit"><Send size={17} /> Send</button>
        </form>
        {feedback && <p className="px-5 pb-5 text-sm font-semibold text-med-muted">{feedback}</p>}
      </section>

      <aside className="grid content-start gap-5">
        <section className="glass-panel p-5">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-black text-med-text">Sources</h2>
            <StatusChip tone="blue">{sources.length}</StatusChip>
          </div>
          <div className="grid gap-3">
            {sources.length === 0 && <p className="text-sm text-med-muted">Sources appear after an answer returns context.</p>}
            {sources.map((source) => (
              <article className="rounded-lg border border-med-border bg-white/70 p-3" key={source}>
                <p className="font-black text-med-text">{source}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="glass-panel p-5">
          <h2 className="mb-4 font-black text-med-text">Current context</h2>
          <div className="grid gap-3 text-sm">
            <p className="flex items-center justify-between"><span className="text-med-muted">Sources</span><strong>{sources.length}</strong></p>
            <p className="flex items-center justify-between"><span className="text-med-muted">Session</span><strong>{sessionId ? "Saved" : "New"}</strong></p>
            <p className="flex items-center justify-between"><span className="text-med-muted">Model</span><strong>{modelUsed || "Waiting"}</strong></p>
          </div>
        </section>
      </aside>
    </div>
  );
}

class MessageRenderBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error) {
    console.error("Markdown message render failed.", error);
  }

  render() {
    if (this.state.hasError) {
      return <p className="whitespace-pre-wrap">{String(this.props.fallback || "")}</p>;
    }
    return this.props.children;
  }
}

function MarkdownMessage({ content }) {
  return (
    <div className="markdown-message">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize]}
      >
        {String(content || "")}
      </ReactMarkdown>
    </div>
  );
}
