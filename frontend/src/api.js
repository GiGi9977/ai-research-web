async function request(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      detail = (await res.json()).detail || detail;
    } catch {}
    throw new Error(detail);
  }
  return res.json();
}

export const getHealth = () => request("/api/health");

export const searchPapers = (q, limit = 10) =>
  request(`/api/search?q=${encodeURIComponent(q)}&limit=${limit}`);

const json = (method, body) => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const listPapers = () => request("/api/papers");
export const getPaper = (id) => request(`/api/papers/${id}`);
export const savePaper = (paper) => request("/api/papers", json("POST", paper));
export const updatePaper = (id, fields) =>
  request(`/api/papers/${id}`, json("PATCH", fields));
export const deletePaper = async (id) => {
  const res = await fetch(`/api/papers/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
};

export const uploadPaper = (file) => {
  const form = new FormData();
  form.append("file", file);
  return request("/api/papers/upload", { method: "POST", body: form });
};

export const summarizePaper = (id, refresh = false) =>
  request(`/api/papers/${id}/summary${refresh ? "?refresh=1" : ""}`, { method: "POST" });
export const askPaper = (id, question) =>
  request(`/api/papers/${id}/ask`, json("POST", { question }));
