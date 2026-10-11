import { useEffect, useRef, useState } from "react";
import { askPaper } from "../api.js";
import RichText from "./RichText.jsx";

const SUGGESTIONS = [
  "What problem does this paper address?",
  "What is the main idea of the proposed approach?",
  "What datasets are used?",
  "What are the major limitations?",
  "How does this method compare with the baselines?",
];

export default function ChatPanel({ paper }) {
  const [messages, setMessages] = useState(paper.messages || []);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest" });
  }, [messages, loading]);

  async function ask(question) {
    const q = question.trim();
    if (!q || loading) return;
    setLoading(true);
    setError("");
    setInput("");
    setMessages((m) => [...m, { id: `tmp-${Date.now()}`, role: "user", content: q }]);
    try {
      const { answer } = await askPaper(paper.id, q);
      setMessages((m) => [...m, { id: `a-${Date.now()}`, role: "assistant", content: answer }]);
    } catch (err) {
      // The server stores nothing on failure, so drop the unanswered question too.
      setMessages((m) => m.slice(0, -1));
      setInput(q);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel">
      <h3>Ask about this paper</h3>
      <div className="chat">
        {messages.map((m) => (
          <div key={m.id} className={`bubble ${m.role}`}>
            <RichText text={m.content} />
          </div>
        ))}
        {loading && <div className="bubble assistant">Thinking…</div>}
        <div ref={endRef} />
      </div>
      {messages.length === 0 && (
        <div className="suggestions">
          {SUGGESTIONS.map((s) => (
            <button key={s} className="secondary" onClick={() => ask(s)} disabled={loading}>
              {s}
            </button>
          ))}
        </div>
      )}
      {error && <p className="error">{error}</p>}
      <form
        className="search-bar"
        onSubmit={(e) => {
          e.preventDefault();
          ask(input);
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question about this paper…"
        />
        <button type="submit" disabled={loading || !input.trim()}>Ask</button>
      </form>
    </section>
  );
}
