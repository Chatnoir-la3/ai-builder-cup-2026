"use client";

import { useState } from "react";

type Message = { role: "user" | "agent"; text: string };

export default function Home() {
  const [sessionId] = useState(() => crypto.randomUUID());
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setMessages((m) => [...m, { role: "user", text }]);
    setInput("");
    setBusy(true);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId, text }),
      });
      const data = (await res.json()) as { reply?: string; error?: string };
      setMessages((m) => [...m, { role: "agent", text: data.reply ?? `Error: ${data.error}` }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col gap-4 p-4">
      <h1 className="text-xl font-semibold">Agent sandbox</h1>
      <ul className="flex flex-1 flex-col gap-2">
        {messages.map((m, i) => (
          <li
            key={i}
            className={`whitespace-pre-wrap rounded-lg p-3 ${m.role === "user" ? "self-end bg-zinc-200" : "bg-white shadow-sm"}`}
          >
            {m.text}
          </li>
        ))}
      </ul>
      <form onSubmit={send} className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="flex-1 rounded-lg border border-zinc-300 bg-white px-3 py-2"
          placeholder="Ask the agent"
        />
        <button disabled={busy} className="rounded-lg bg-zinc-900 px-4 py-2 text-white disabled:opacity-50">
          {busy ? "..." : "Send"}
        </button>
      </form>
    </main>
  );
}
