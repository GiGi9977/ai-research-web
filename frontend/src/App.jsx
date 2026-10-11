import { useState } from "react";
import LibraryPage from "./pages/LibraryPage.jsx";
import SearchPage from "./pages/SearchPage.jsx";

export default function App() {
  const [tab, setTab] = useState("search");

  return (
    <main className="app">
      <h1>AI Research Assistant</h1>
      <nav className="tabs">
        <button className={tab === "search" ? "active" : ""} onClick={() => setTab("search")}>
          Search
        </button>
        <button className={tab === "library" ? "active" : ""} onClick={() => setTab("library")}>
          Library
        </button>
      </nav>
      {tab === "search" ? <SearchPage /> : <LibraryPage />}
    </main>
  );
}
