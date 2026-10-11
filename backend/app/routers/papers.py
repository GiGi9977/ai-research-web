from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Paper
from app.schemas import PaperDetail, PaperIn, PaperOut, PaperPatch
from app.services.metadata import extract_metadata
from app.services.pdf import MAX_PDF_BYTES, PdfError, download_pdf_text, extract_text
from app.services.pdf_sources import fallback_pdf_urls

router = APIRouter(prefix="/api/papers")


def _get_or_404(db: Session, paper_id: int) -> Paper:
    paper = db.get(Paper, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper


def _out(paper: Paper, model=PaperOut):
    out = model.model_validate(paper)
    out.has_full_text = bool(paper.full_text)
    out.has_summary = bool(paper.summary)
    return out


@router.get("", response_model=list[PaperOut], response_model_by_alias=True)
def list_papers(db: Session = Depends(get_db)):
    papers = db.scalars(select(Paper).order_by(Paper.created_at.desc(), Paper.id.desc()))
    return [_out(p) for p in papers]


@router.post("/upload", response_model=PaperOut, response_model_by_alias=True, status_code=201)
async def upload_paper(file: UploadFile = File(...), db: Session = Depends(get_db)):
    data = await file.read(MAX_PDF_BYTES + 1)
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDF is larger than 30 MB")
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="File is not a PDF")
    try:
        full_text = extract_text(data)
    except PdfError as e:
        raise HTTPException(status_code=422, detail=str(e))

    meta = await extract_metadata(data)
    fallback_title = (file.filename or "Untitled upload").rsplit(".", 1)[0]
    paper = Paper(
        source="upload",
        title=meta["title"] or fallback_title,
        authors=meta["authors"],
        year=meta["year"],
        abstract=meta["abstract"],
        full_text=full_text,
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)
    return _out(paper)


@router.get("/{paper_id}", response_model=PaperDetail, response_model_by_alias=True)
def get_paper(paper_id: int, db: Session = Depends(get_db)):
    return _out(_get_or_404(db, paper_id), PaperDetail)


@router.post("", response_model=PaperOut, response_model_by_alias=True)
async def save_paper(body: PaperIn, response: Response, db: Session = Depends(get_db)):
    if body.external_id:
        existing = db.scalar(select(Paper).where(Paper.external_id == body.external_id))
        if existing:
            response.status_code = 200
            return _out(existing)

    full_text, pdf_url = None, body.pdf_url
    if pdf_url:
        full_text = await download_pdf_text(pdf_url)
    if not full_text:
        for candidate in await fallback_pdf_urls(body.title, body.url):
            if full_text := await download_pdf_text(candidate):
                pdf_url = candidate
                break
    paper = Paper(
        external_id=body.external_id,
        source=body.source,
        title=body.title,
        authors=body.authors,
        year=body.year,
        abstract=body.abstract,
        url=body.url,
        pdf_url=pdf_url,
        full_text=full_text,
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)
    response.status_code = 201
    return _out(paper)


@router.patch("/{paper_id}", response_model=PaperOut, response_model_by_alias=True)
def update_paper(paper_id: int, body: PaperPatch, db: Session = Depends(get_db)):
    paper = _get_or_404(db, paper_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "title" and value is None:
            continue
        setattr(paper, field, value)
    db.commit()
    db.refresh(paper)
    return _out(paper)


@router.delete("/{paper_id}", status_code=204)
def delete_paper(paper_id: int, db: Session = Depends(get_db)):
    db.delete(_get_or_404(db, paper_id))
    db.commit()
