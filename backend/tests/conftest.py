"""Shared fixtures: an isolated SQLite database per test and no real network access."""
import pymupdf
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db import Base, get_db
from app.main import app


@pytest.fixture(autouse=True)
def safe_settings(monkeypatch):
    # Never use the developer's real keys/services from backend/.env during tests.
    monkeypatch.setattr(settings, "openai_api_key", "")
    monkeypatch.setattr(settings, "grobid_url", "http://grobid.test")
    monkeypatch.setattr(settings, "openalex_mailto", "")
    monkeypatch.setattr(settings, "unpaywall_email", "")


@pytest.fixture(autouse=True)
def no_network():
    # Any HTTP request that a test did not explicitly mock fails loudly.
    with respx.mock(assert_all_called=False) as router:
        yield router


@pytest.fixture
def session_factory(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def _fk(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False)
    engine.dispose()


@pytest.fixture
def client(session_factory):
    def _get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def make_pdf(
    lines: list[tuple[str, float]], pages: int = 1, metadata: dict | None = None
) -> bytes:
    """Build a real PDF. `lines` is [(text, font_size)] drawn top to bottom on page 1."""
    doc = pymupdf.open()
    if metadata:
        doc.set_metadata(metadata)
    page = doc.new_page()
    y = 72
    for text, size in lines:
        page.insert_text((72, y), text, fontsize=size)
        y += size * 1.6
    for _ in range(pages - 1):
        doc.new_page().insert_text((72, 72), "More body text on a later page. " * 3, fontsize=10)
    data = doc.tobytes()
    doc.close()
    return data


BODY = "This paper studies an important problem in machine learning research. " * 5


@pytest.fixture
def sample_pdf() -> bytes:
    return make_pdf(
        [
            ("Deep Learning for Paper Summaries", 20),
            ("Alice Smith, Bob Jones", 12),
            ("Abstract", 11),
            ("We propose a method that summarizes papers. It works well.", 10),
            ("1 Introduction", 11),
            (BODY[:90], 10),
            (BODY[90:180], 10),
            (BODY[180:270], 10),
            ("Published 2021.", 10),
        ]
    )


@pytest.fixture
def anyio_backend():
    return "asyncio"


PUBLIC_IP = "93.184.216.34"


@pytest.fixture
def fake_dns(monkeypatch):
    """Deterministic DNS for the SSRF check: *.internal resolve to private IPs."""
    import socket

    from app.services import pdf

    table = {"localhost": "127.0.0.1", "intranet.internal": "10.0.0.5", "meta.internal": "169.254.169.254"}

    def getaddrinfo(host, *_a, **_k):
        if host == "nxdomain.test":
            raise socket.gaierror("not found")
        ip = table.get(host, PUBLIC_IP)
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]

    monkeypatch.setattr(pdf.socket, "getaddrinfo", getaddrinfo)
