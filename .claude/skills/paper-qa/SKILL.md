---
name: paper-qa
description: Work on question answering about a selected paper. Use when changing the Q&A prompt, chat history handling, or answer grounding.
---

# Paper Q&A

- Code: `answer` in `backend/app/services/llm.py`; route `POST /api/papers/{id}/ask` with body `{question}` in `backend/app/routers/llm.py`.
- The system prompt contains the paper (same `paper_context` as summaries) and tells the model to answer only from the paper, to interpret short questions charitably ("what is gap" = the research gap), and, when the answer is not in the paper, to say it could not find it, say what kind of paper it is if that explains it (e.g. a conceptual or position paper with no datasets or experiments), and give the closest relevant information. A bare "The paper does not say." was too curt and too literal; keep the no-invention rule.
- History: earlier turns are loaded from the `messages` table and sent before the new question, so follow-ups work. Both the question and the answer are stored after a successful call.
- A failed LLM call stores nothing, so history never contains unanswered questions.
- Good test questions: the problem addressed, main idea, datasets used, limitations, comparison with baselines.
- Frontend: `ChatPanel.jsx` (message list, input, suggested questions, loading state).
