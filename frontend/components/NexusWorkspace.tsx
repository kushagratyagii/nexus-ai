"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import {
  Activity, ArrowDown, ArrowUp, Bot, Check, CheckCheck, ChevronDown,
  CircleHelp, FileText, FolderOpen, LoaderCircle, Menu, MessageSquare,
  MoreHorizontal, Paperclip, Plus, RefreshCw, Search, Send, Settings2,
  ShieldCheck, Sparkles, Trash2, UploadCloud, X, Zap
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const API = (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

type Conversation = {
  thread_id: string;
  title: string;
  created_at: string;
  updated_at: string;
};
type Message = {
  type: string;
  content: string | Array<{ type?: string; text?: string }>;
  tool_calls?: Array<{ name: string; args?: Record<string, unknown> }>;
};
type Approval = { type?: string; action?: string; details?: string; message?: string };

function messageText(content: Message["content"]) {
  if (typeof content === "string") return content;
  return content.map((part) => part.text || "").join("");
}
function shortDate(value: string) {
  try {
    return new Date(value).toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch { return ""; }
}

export default function NexusWorkspace() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [approval, setApproval] = useState<Approval | null>(null);
  const [notice, setNotice] = useState("");
  const [uploading, setUploading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [search, setSearch] = useState("");
  const [menuId, setMenuId] = useState("");
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const activeConversation = conversations.find((c) => c.thread_id === activeId);

  const request = useCallback(async (path: string, options?: RequestInit) => {
    const response = await fetch(`${API}${path}`, {
      ...options,
      headers: { ...(options?.body instanceof FormData ? {} : { "Content-Type": "application/json" }), ...options?.headers },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || data.message || `Request failed (${response.status})`);
    return data;
  }, []);

  const loadConversations = useCallback(async () => {
    try {
      const data = await request("/api/conversations");
      setConversations(data.conversations || []);
      setApiOnline(true);
      return data.conversations as Conversation[];
    } catch (error) {
      setApiOnline(false);
      setNotice(error instanceof Error ? error.message : "Could not reach the API");
      return [];
    }
  }, [request]);

  const loadHistory = useCallback(async (threadId: string) => {
    try {
      const data = await request(`/api/conversations/${threadId}`);
      setMessages(data.messages || []);
      setApproval(null);
    } catch (error) {
      setMessages([]);
      setNotice(error instanceof Error ? error.message : "Could not load conversation");
    }
  }, [request]);

  useEffect(() => { void loadConversations(); }, [loadConversations]);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, busy, approval]);

  async function newConversation() {
    setNotice("");
    try {
      const data = await request("/api/conversations", {
        method: "POST", body: JSON.stringify({ title: "New conversation" }),
      });
      const conversation = data.conversation as Conversation;
      setConversations((old) => [conversation, ...old]);
      setActiveId(conversation.thread_id);
      setMessages([]);
      setApproval(null);
      setInput("");
      setSidebarOpen(true);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not create conversation");
    }
  }

  async function selectConversation(conversation: Conversation) {
    setActiveId(conversation.thread_id);
    setMenuId("");
    await loadHistory(conversation.thread_id);
  }

  async function renameConversation(conversation: Conversation) {
    const title = window.prompt("Rename conversation", conversation.title);
    if (!title?.trim()) return;
    try {
      const data = await request(`/api/conversations/${conversation.thread_id}`, {
        method: "PATCH", body: JSON.stringify({ title: title.trim() }),
      });
      setConversations((old) => old.map((c) => c.thread_id === conversation.thread_id ? data.conversation : c));
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Rename failed");
    }
    setMenuId("");
  }

  async function removeConversation(conversation: Conversation) {
    if (!window.confirm(`Delete "${conversation.title}" and its saved agent memory? This cannot be undone.`)) return;
    try {
      await request(`/api/conversations/${conversation.thread_id}`, { method: "DELETE" });
      setConversations((old) => old.filter((c) => c.thread_id !== conversation.thread_id));
      if (activeId === conversation.thread_id) {
        setActiveId(""); setMessages([]); setApproval(null);
      }
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Delete failed");
    }
    setMenuId("");
  }

  
async function sendMessage(event?: FormEvent) {
  event?.preventDefault();

  const text = input.trim();
  if (!text || busy) return;

  let threadId = activeId;

  if (!threadId) {
    try {
      const created = await request("/api/conversations", {
        method: "POST",
        body: JSON.stringify({
          title: text.slice(0, 42) || "New conversation",
        }),
      });

      const conversation = created.conversation as Conversation;
      threadId = conversation.thread_id;

      setActiveId(threadId);
      setConversations((old) => [conversation, ...old]);
    } catch (error) {
      setNotice(
        error instanceof Error ? error.message : "Could not start chat"
      );
      return;
    }
  }

  setInput("");
  setNotice("");
  setApproval(null);

  // Add the user message and an empty assistant placeholder.
  setMessages((old) => [
    ...old,
    { type: "human", content: text },
    { type: "ai", content: "" },
  ]);

  setBusy(true);

  try {
    // Use fetch directly because the normal request helper parses JSON.
    const response = await fetch(`${API}/api/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      },
      body: JSON.stringify({
        message: text,
        thread_id: threadId,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(
        errorData.detail || `Request failed (${response.status})`
      );
    }

    if (!response.body) {
      throw new Error("Streaming response body is unavailable.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let streamFinished = false;

    while (!streamFinished) {
      const { value, done } = await reader.read();

      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Process complete SSE events while retaining incomplete chunks.
      let boundary: number;

      while ((boundary = buffer.indexOf("\n\n")) !== -1) {
        const rawEvent = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);

        const dataLine = rawEvent
          .split(/\r?\n/)
          .find((line) => line.startsWith("data:"));

        if (!dataLine) continue;

        const payload = JSON.parse(dataLine.slice(5).trim());

        if (payload.type === "token") {
          const token = payload.content || "";

          setMessages((old) => {
            const updated = [...old];
            const last = updated[updated.length - 1];

            if (last?.type === "ai") {
              updated[updated.length - 1] = {
                ...last,
                content: messageText(last.content) + token,
              };
            }

            return updated;
          });
        }

        else if (payload.type === "approval_required") {
          setMessages((old) => {
            const updated = [...old];
            const last = updated[updated.length - 1];

            if (last?.type === "ai" && !messageText(last.content)) {
              updated.pop();
            }

            return updated;
          });

          setApproval(payload.interrupt || {});
          streamFinished = true;
          break;
        }

        else if (payload.type === "error") {
          throw new Error(payload.message || "Streaming failed.");
        }

        else if (payload.type === "done") {
          streamFinished = true;
          break;
        }
      }
    }

    await loadConversations();

  } catch (error) {
    setMessages((old) => {
      const updated = [...old];
      const last = updated[updated.length - 1];

      const errorMessage =
        error instanceof Error ? error.message : "Please try again.";

      if (last?.type === "ai" && !messageText(last.content)) {
        updated[updated.length - 1] = {
          type: "ai",
          content: `I couldn't complete that request. ${errorMessage}`,
        };
      } else {
        updated.push({
          type: "ai",
          content: `Streaming interrupted. ${errorMessage}`,
        });
      }

      return updated;
    });

  } finally {
    setBusy(false);
  }
}


  async function decideApproval(decision: "approve" | "reject") {
    if (!activeId || busy) return;
    setBusy(true);
    try {
      const data = await request("/api/chat/resume", {
        method: "POST", body: JSON.stringify({ thread_id: activeId, decision }),
      });
      setApproval(data.status === "approval_required" ? data.interrupt : null);
      if (data.status === "completed") {
        setMessages((old) => [...old, { type: "ai", content: data.response || "The operation has completed." }]);
      }
      await loadConversations();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Could not resume agent");
    } finally {
      setBusy(false);
    }
  }

  async function uploadPdf(file?: File) {
    if (!file) return;
    if (!activeId) {
      setNotice("Create or select a conversation before uploading a PDF.");
      return;
    }
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setNotice("Only PDF files are supported.");
      return;
    }
    setUploading(true);
    setNotice("");
    try {
      const form = new FormData();
      form.append("file", file);
      const data = await request("/api/rag/upload", { method: "POST", body: form });
      setMessages((old) => [...old, { type: "system", content: `Document indexed: ${file.name}. ${data.message || "You can now ask questions about it."}` }]);
      setShowUpload(false);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "PDF upload failed");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  const filtered = conversations.filter((c) => c.title.toLowerCase().includes(search.toLowerCase()));

  return (
    <main className="nexus-shell">
      <aside className={`sidebar ${sidebarOpen ? "sidebar-open" : "sidebar-closed"}`}>
        <div className="brand">
          <div className="brand-mark"><Sparkles size={19} /></div>
          <div><div className="brand-name">NEXUS<span>AI</span></div><div className="brand-caption">AGENTIC WORKSPACE</div></div>
          <button className="icon-btn sidebar-close" onClick={() => setSidebarOpen(false)} aria-label="Close sidebar"><X size={17}/></button>
        </div>

        <button className="new-chat-btn" onClick={newConversation}><Plus size={17}/> New conversation <span>⌘ K</span></button>

        <div className="side-label">WORKSPACE</div>
        <div className="nav-item active"><MessageSquare size={16}/> Conversations <span className="nav-count">{conversations.length}</span></div>
        <button className={`nav-item ${showUpload ? "active" : ""}`} onClick={() => setShowUpload((v) => !v)}><FolderOpen size={16}/> Knowledge base <span className="nav-dot"/></button>
        {showUpload && (
          <div className="upload-mini">
            <p>Upload a PDF to your agent&apos;s knowledge base.</p>
            <button className="upload-mini-btn" onClick={() => fileRef.current?.click()} disabled={uploading}>
              {uploading ? <LoaderCircle className="spin" size={15}/> : <UploadCloud size={15}/>}
              {uploading ? "Indexing..." : "Choose PDF"}
            </button>
          </div>
        )}

        <div className="history-heading"><span className="side-label">RECENT CHATS</span><button className="icon-btn tiny" onClick={() => void loadConversations()} title="Refresh"><RefreshCw size={14}/></button></div>
        <div className="search-box"><Search size={14}/><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search conversations"/></div>
        <div className="conversation-list">
          {filtered.map((conversation) => (
            <div className={`conversation-row ${activeId === conversation.thread_id ? "selected" : ""}`} key={conversation.thread_id}>
              <button className="conversation-select" onClick={() => void selectConversation(conversation)}>
                <MessageSquare size={15}/><span>{conversation.title}</span>
              </button>
              <button className="icon-btn tiny more-btn" onClick={() => setMenuId(menuId === conversation.thread_id ? "" : conversation.thread_id)} aria-label="Conversation options"><MoreHorizontal size={16}/></button>
              {menuId === conversation.thread_id && (
                <div className="context-menu">
                  <button onClick={() => void renameConversation(conversation)}><FileText size={14}/> Rename</button>
                  <button className="danger" onClick={() => void removeConversation(conversation)}><Trash2 size={14}/> Delete</button>
                </div>
              )}
            </div>
          ))}
          {filtered.length === 0 && <div className="empty-side">{search ? "No matching conversations" : "Your conversations will appear here."}</div>}
        </div>

        <div className="sidebar-bottom">
          <div className="api-card">
            <div className="api-card-top"><span className={`status-led ${apiOnline ? "online" : apiOnline === false ? "offline" : ""}`}/><span>BACKEND API</span><strong>{apiOnline ? "Connected" : apiOnline === false ? "Offline" : "Checking"}</strong></div>
            <div className="api-url">{API}</div>
          </div>
          <div className="profile-row"><div className="avatar-small">N</div><div><strong>NEXUS Workspace</strong><span>Local development</span></div><Settings2 size={16}/></div>
        </div>
      </aside>

      <section className="main-panel">
        <header className="topbar">
          <div className="topbar-left">
            {!sidebarOpen && <button className="icon-btn" onClick={() => setSidebarOpen(true)} aria-label="Open sidebar"><Menu size={19}/></button>}
            <div className="crumb"><span>Workspace</span><b>/</b><strong>{activeConversation?.title || "New conversation"}</strong></div>
          </div>
          <div className="topbar-right">
            <div className="model-chip"><span className="model-led"/> GPT-4.1 MINI</div>
            <div className="secure-chip"><ShieldCheck size={14}/> Private session</div>
          </div>
        </header>

        <div className="chat-scroll">
          <div className={`welcome ${messages.length ? "welcome-compact" : ""}`}>
            <div className="welcome-orb"><div className="orb-core"><Sparkles size={24}/></div></div>
            <div className="eyebrow"><span/> YOUR AGENTIC AI WORKSPACE</div>
            <h1>{messages.length ? "Where should we go next?" : <>Build ideas into <em>intelligence.</em></>}</h1>
            {!messages.length && <p>One workspace. Multiple capabilities. Ask questions, retrieve knowledge, and let your agent take action with human oversight.</p>}
            {!messages.length && (
              <div className="capability-grid">
                <button onClick={() => setInput("Summarize the key ideas from my uploaded documents.")}><FileText size={17}/><span><b>Knowledge retrieval</b><small>Ask questions about PDFs</small></span></button>
                <button onClick={() => setInput("What tools can you use, and when should you use them?")}><Zap size={17}/><span><b>Agentic tools</b><small>Reason and use MCP tools</small></span></button>
                <button onClick={() => setInput("Explain how human approval works in this agent.")}><ShieldCheck size={17}/><span><b>Human oversight</b><small>Approve sensitive actions</small></span></button>
              </div>
            )}
          </div>

          {messages.map((message, index) => (
            <div className={`message-row ${message.type === "human" ? "user-row" : ""}`} key={`${index}-${message.type}`}>
              {message.type === "system" ? (
                <div className="system-message"><CheckCircleIcon/> {messageText(message.content)}</div>
              ) : (
                <>
                  <div className={`message-avatar ${message.type === "human" ? "user-avatar" : ""}`}>{message.type === "human" ? "Y" : <Sparkles size={16}/>}</div>
                  <div className="message-body">
                    <div className="message-meta"><strong>{message.type === "human" ? "You" : "NEXUS"}</strong><span>{message.type === "human" ? "USER" : "AGENT RESPONSE"}</span></div>
                    <div className="markdown-content"><ReactMarkdown remarkPlugins={[remarkGfm]}>{messageText(message.content)}</ReactMarkdown></div>
                  </div>
                </>
              )}
            </div>
          ))}

          {approval && (
            <div className="approval-card">
              <div className="approval-icon"><ShieldCheck size={20}/></div>
              <div className="approval-content">
                <div className="approval-label">HUMAN APPROVAL REQUIRED</div>
                <h3>The agent needs your permission</h3>
                <p>{approval.message || "Review this action before the agent continues."}</p>
                <div className="approval-detail"><span>REQUESTED ACTION</span><strong>{approval.action || "Protected operation"}</strong><small>{approval.details || "No additional details provided."}</small></div>
                <div className="approval-actions">
                  <button className="reject-btn" onClick={() => void decideApproval("reject")} disabled={busy}>Reject</button>
                  <button className="approve-btn" onClick={() => void decideApproval("approve")} disabled={busy}>{busy ? <LoaderCircle className="spin" size={15}/> : <Check size={15}/>} Approve action</button>
                </div>
              </div>
            </div>
          )}

          {busy && <div className="thinking-row"><div className="message-avatar"><Sparkles size={16}/></div><div><span className="thinking-dots"><i/><i/><i/></span><small>NEXUS is thinking</small></div></div>}
          <div ref={bottomRef}/>
        </div>

        <div className="composer-wrap">
          {notice && <div className="notice"><CircleHelp size={14}/>{notice}<button onClick={() => setNotice("")}><X size={14}/></button></div>}
          <form className="composer" onSubmit={sendMessage}>
            <textarea value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void sendMessage(); } }} placeholder="Message your agent..." rows={1} disabled={busy}/>
            <div className="composer-bottom">
              <div className="composer-tools">
                <button type="button" className="tool-btn" onClick={() => fileRef.current?.click()} title="Upload PDF"><Paperclip size={16}/> <span>Attach PDF</span></button>
                <span className="composer-divider"/>
                <span className="composer-hint"><ShieldCheck size={13}/> Human oversight enabled</span>
              </div>
              <button type="submit" className="send-btn" disabled={!input.trim() || busy} aria-label="Send message">{busy ? <LoaderCircle className="spin" size={17}/> : <ArrowUp size={18}/>}</button>
            </div>
          </form>
          <div className="disclaimer">NEXUS can make mistakes. Review important information and approve sensitive actions.</div>
        </div>
      </section>
      <input ref={fileRef} type="file" accept="application/pdf,.pdf" hidden onChange={(e) => void uploadPdf(e.target.files?.[0])}/>
    </main>
  );
}

function CheckCircleIcon() {
  return <span className="system-check"><Check size={13}/></span>;
}
