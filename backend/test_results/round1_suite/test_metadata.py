"""Round 1: services/metadata.py (GROBID TEI parsing, heuristics, merging)."""
import httpx
import pytest

from app.services import metadata
from app.services.metadata import extract_metadata, heuristic_metadata, parse_grobid_tei

from .conftest import BODY, make_pdf

pytestmark = pytest.mark.anyio

GROBID = "http://grobid.test/api/processHeaderDocument"


def tei(title="Graph Neural Networks", authors=(("Jane", "Q", "Doe"),), when="2019-05-01", abstract="We study GNNs."):
    auth = "".join(
        "<author><persName>"
        + "".join(f"<forename>{f}</forename>" for f in names[:-1])
        + f"<surname>{names[-1]}</surname></persName></author>"
        for names in authors
    )
    date = f'<date when="{when}"/>' if when else ""
    abs_ = f"<abstract><p>{abstract}</p></abstract>" if abstract else ""
    return f"""<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader>
      <fileDesc><titleStmt><title level="a" type="main">{title}</title></titleStmt>
      <publicationStmt>{date}</publicationStmt>
      <sourceDesc><biblStruct><analytic>{auth}</analytic></biblStruct></sourceDesc></fileDesc>
      <profileDesc>{abs_}</profileDesc></teiHeader></TEI>"""


def test_parse_grobid_tei_full():
    meta = parse_grobid_tei(tei(authors=(("Jane", "Q", "Doe"), ("John", "Roe"))))
    assert meta == {
        "title": "Graph Neural Networks",
        "authors": ["Jane Q Doe", "John Roe"],
        "year": 2019,
        "abstract": "We study GNNs.",
    }


def test_parse_grobid_tei_missing_fields():
    meta = parse_grobid_tei(tei(title="", authors=(), when="", abstract=""))
    assert meta == {"title": "", "authors": [], "year": None, "abstract": None}


def test_heuristic_metadata(sample_pdf):
    meta = heuristic_metadata(sample_pdf)
    assert meta["title"] == "Deep Learning for Paper Summaries"
    assert meta["authors"] == ["Alice Smith", "Bob Jones"]
    assert meta["year"] == 2021
    assert meta["abstract"] == "We propose a method that summarizes papers. It works well."


def test_heuristic_skips_affiliations_and_joins_wrapped_title():
    pdf = make_pdf(
        [
            ("Journal of Things", 9),
            ("A Very Long Title That", 18),
            ("Wraps Onto Two Lines", 18),
            ("Carol King1 and Dan Brown2", 11),
            ("1 Purdue University, West Lafayette", 9),
            ("Abstract: Short abstract here.", 10),
            ("Keywords: things", 10),
            (BODY[:90], 10),
            (BODY[90:180], 10),
        ]
    )
    meta = heuristic_metadata(pdf)
    assert meta["title"] == "A Very Long Title That Wraps Onto Two Lines"
    assert meta["authors"] == ["Carol King", "Dan Brown"]
    assert meta["abstract"] == "Short abstract here."


def test_heuristic_year_falls_back_to_creation_date():
    pdf = make_pdf([("A Title With Words", 18), (BODY[:90], 10)], metadata={"creationDate": "D:20180304120000"})
    assert heuristic_metadata(pdf)["year"] == 2018


async def test_extract_metadata_prefers_grobid_and_fills_gaps(no_network, sample_pdf):
    no_network.post(GROBID).respond(text=tei(abstract="", when=""))
    meta = await extract_metadata(sample_pdf)
    assert meta["title"] == "Graph Neural Networks"
    assert meta["authors"] == ["Jane Q Doe"]
    assert meta["year"] == 2021  # missing in GROBID -> heuristic
    assert meta["abstract"].startswith("We propose a method")  # missing in GROBID -> heuristic
    assert no_network.calls.last.request.headers["accept"] == "application/xml"


async def test_extract_metadata_grobid_without_title_uses_heuristics(no_network, sample_pdf):
    no_network.post(GROBID).respond(text=tei(title=""))
    meta = await extract_metadata(sample_pdf)
    assert meta == heuristic_metadata(sample_pdf)


@pytest.mark.parametrize("response", [dict(status_code=503), dict(text="<not-xml")])
async def test_extract_metadata_grobid_failure(no_network, sample_pdf, response):
    no_network.post(GROBID).respond(**response)
    assert await extract_metadata(sample_pdf) == heuristic_metadata(sample_pdf)
