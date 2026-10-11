---
name: paper-qa
description: Work on question answering about a selected paper. Use when changing the Q&A prompt, chat history handling, or answer grounding.
---

# Paper Q&A

- Code: `answer` in `backend/app/services/llm.py`; route `POST /api/papers/{id}/ask` with body `{question}` in `backend/app/routers/llm.py`.
- The system prompt contains the paper (same `paper_context` as summaries) and tells the model to answer only from the paper and to say so when the answer is not there.
- History: earlier turns are loaded from the `messages` table and sent before the new question, so follow-ups work. Both the question and the answer are stored after a successful call.
- A failed LLM call stores nothing, so history never contains unanswered questions.
- Good test questions: the problem addressed, main idea, datasets used, limitations, comparison with baselines.
- Frontend: `ChatPanel.jsx` (message list, input, suggested questions, loading state).
