import csv

from grepleo.matching import evaluate
from grepleo.models import Fit, Job, WorkMode
from grepleo.panorama import Panorama, build_panorama, count_requirements
from grepleo.profiles import Category, Profile
from grepleo.report import export_csv, export_html

TEXT = "Scrum, Power BI y SQL. Inglés C1. 5 años de experiencia. " * 4


def jobs():
    return [
        Job(key="indeed:1", source="indeed", title="Product Owner Data", company="ERNI Spain", location="Madrid",
            work_mode=WorkMode.HYBRID, description=TEXT, full_description=True, url="https://es.indeed.com/x",
            posted="2026-10-23", salary_min=50000.0, salary_max=60000.0, salary_text="50.000–60.000 €"),
        Job(key="infojobs:2", source="infojobs", title="=cmd|' /C calc'!A0", company="+Evil", location="Madrid",
            description="Scrum", full_description=False, url="javascript:alert(1)", closed=True),
    ]


def profile():
    return Profile(name="PO", headline="CRM Manager", years=8, must=["Scrum"], nice=["Snowflake"],
                   languages={"Inglés": "C1"}, categories=[Category("Data PO", ["data"])])


def evaluations(jobs_list, prof):
    return {job.key: evaluate(job, prof) for job in jobs_list}


def test_requirement_counts_only_use_jobs_with_a_full_description():
    counts = {item.name: item.count for item in count_requirements(jobs(), profile())}
    assert counts["Scrum"] == 1 and counts["Power BI"] == 1 and counts["AWS"] == 0 and counts["Snowflake"] == 0
    assert counts["Inglés"] == 1
    assert count_requirements([], profile())[0].count == 0


def test_the_panorama_states_only_what_counting_can_support():
    sample, prof = jobs(), profile()
    panorama = build_panorama(sample, evaluations(sample, prof), prof)
    assert (panorama.total, panorama.detailed) == (2, 1)
    text = "\n".join(panorama.insights)
    assert "Lo más pedido" in text and "Ninguna oferta con detalle cita" in text
    assert "Encaje:" in text and "1 de 2 ofertas publican salario" in text and "1 oferta es una ficha resumida" in text
    assert build_panorama([], {}, prof).insights == []


def test_csv_export_neutralizes_formulas(tmp_path):
    sample, prof = jobs(), profile()
    path = tmp_path / "ofertas.csv"
    export_csv(path, sample, evaluations(sample, prof), {"indeed": "Indeed", "infojobs": "InfoJobs"})
    rows = list(csv.reader(path.open(encoding="utf-8-sig")))
    assert rows[0][:3] == ["Empresa", "Puesto", "Tipo"] and rows[1][0] == "ERNI Spain" and rows[1][2] == "Data PO"
    assert rows[2][0].startswith("'+") and rows[2][1].startswith("'=")


def test_html_report_is_escaped_self_contained_and_marks_summaries_and_closed_jobs(tmp_path):
    sample, prof = jobs(), profile()
    results = evaluations(sample, prof)
    path = tmp_path / "informe.html"
    export_html(path, prof, sample, results, build_panorama(sample, results, prof),
                {"indeed": "Indeed", "infojobs": "InfoJobs"}, "Radar de ofertas")
    page = path.read_text(encoding="utf-8")
    assert "<title>Radar de ofertas</title>" in page and "CRM Manager" in page
    assert "ERNI Spain" in page and 'href="https://es.indeed.com/x"' in page
    assert "javascript:alert" not in page.replace("&lt;", "")      # un enlace que no es http(s) no se enlaza
    assert "&#x27; /C calc" in page or "&#x27;" in page            # el texto de las ofertas va escapado
    assert "Ficha resumida" in page and "Posiblemente cerrada" in page and "Publicada el 2026-10-23" in page
    assert 'data-fit="' in page and "<script>" in page and "src=" not in page    # sin recursos externos
    assert Fit.HIGH.value in page or Fit.MEDIUM.value in page


def test_html_report_without_profile_or_jobs(tmp_path):
    path = tmp_path / "vacio.html"
    export_html(path, None, [], {}, Panorama(0, 0, [], []), {}, "Vacío")
    assert "<tbody></tbody>" in path.read_text(encoding="utf-8")
