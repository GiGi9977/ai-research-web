from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.routers import llm, papers, search


@asynccontextmanager
async def lifespan(_):
    init_db()
    yield


app = FastAPI(title="AI Research Assistant", lifespan=lifespan)
app.include_router(search.router)
app.include_router(papers.router)
app.include_router(llm.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}
