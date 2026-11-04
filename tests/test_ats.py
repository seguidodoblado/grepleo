import zipfile

from grepleo.ats import KNOCKOUT_FACTOR, LIKELY, POSSIBLE, AtsEstimate, estimate_ats
from grepleo.cv import uploaded_cv_text
from grepleo.models import Job
from grepleo.profiles import Profile

OFFER = """Buscamos un perfil DevOps para plataforma cloud.

Requisitos:
- Experiencia con AWS y Docker
- Python y Bash
- Al menos 2 años de experiencia

Se valorará:
- Terraform
- Kubernetes
"""


def job(**changes):
    base = {"key": "x:1", "source": "x", "title": "Ingeniero DevOps Cloud", "description": OFFER * 2,
            "full_description": True}
    base.update(changes)
    return Job(**base)


def good_profile(**changes):
    base = {"name": "p", "full_name": "Ana", "headline": "Ingeniera DevOps Cloud", "years": 4, "studies": "degree",
            "education": "Grado en Informática", "languages": {"Inglés": "B2"},
            "must": ["AWS", "Docker", "Python", "Bash"], "nice": ["Terraform", "Kubernetes"],
            "experience": "**DevOps** · ACME · 2022-2026\n- Pipelines en AWS con Docker y Terraform"}
    base.update(changes)
    return Profile(**base)


def test_a_cv_that_cites_the_offers_keywords_and_has_every_section_scores_high():
    estimate = estimate_ats(job(), good_profile())
    assert estimate.percent >= LIKELY and estimate.keyword_score == 1 and estimate.format_score == 1
    assert estimate.missing == [] and estimate.failed == [] and estimate.reliability == "high"
    assert estimate.found[0] in ("AWS", "Docker", "Python", "Bash")           # las que se piden como requisito, primero
    assert "probable" in estimate.verdict


def test_missing_keywords_lower_the_score_and_the_most_wanted_ones_are_listed_first():
    profile = good_profile(must=["AWS"], nice=[], experience="**Soporte** · ACME · 2022-2026\n- Atención al cliente")
    estimate = estimate_ats(job(), profile)
    assert estimate.percent < estimate_ats(job(), good_profile()).percent
    assert estimate.keyword_score < 1 and "AWS" in estimate.found
    assert estimate.missing.index("Docker") < estimate.missing.index("Terraform")      # requisito antes que deseable
    assert "Kubernetes" in estimate.missing


def test_a_missing_requirement_multiplies_the_result_and_experience_weighs_by_the_years_that_are_missing():
    from grepleo.ats import EXPERIENCE_FACTORS, experience_factor
    assert experience_factor(1) == 0.85 and experience_factor(2) == 0.7 and experience_factor(3) == KNOCKOUT_FACTOR
    assert experience_factor(10) == KNOCKOUT_FACTOR and EXPERIENCE_FACTORS == ((1, 0.85), (2, 0.7))
    ok = estimate_ats(job(), good_profile())
    short = estimate_ats(job(), good_profile(years=1))                  # pide 2 años y tiene 1: falta 1
    assert short.failed == ["Experiencia"] and short.factors == [0.85] and short.keyword_score == ok.keyword_score
    assert abs(short.percent - ok.percent * 0.85) < 1.5
    far = estimate_ats(job(description=OFFER.replace("2 años", "5 años") * 2), good_profile(years=1))   # faltan 4
    assert far.factors == [KNOCKOUT_FACTOR] and far.percent < short.percent
    middle = estimate_ats(job(description=OFFER.replace("2 años", "3 años") * 2), good_profile(years=1))  # faltan 2
    assert middle.factors == [0.7]
    english = estimate_ats(job(description=OFFER * 2 + "\nSe requiere inglés C1.\n"), good_profile(languages={}))
    assert english.failed == ["Inglés C1"] and english.factors == [KNOCKOUT_FACTOR]   # idiomas y estudios: el factor fijo
    assert len(english.failed) == len(english.factors)


def test_a_summary_card_has_low_reliability_and_no_keyword_score():
    summary = job(full_description=False, description="Scrum", experience_text="Al menos 2 años")
    estimate = estimate_ats(summary, good_profile())
    assert estimate.reliability == "low" and estimate.keyword_score is None
    assert 0 <= estimate.percent <= 100 and estimate.unknown >= 0


def test_the_title_and_the_structure_count():
    bare = Profile(name="vacío")
    estimate = estimate_ats(job(), bare)
    assert estimate.format_score == 0 and estimate.title_score == 0 and estimate.percent < POSSIBLE
    assert "poco probable" in estimate.verdict
    assert estimate_ats(job(), good_profile(headline="Ingeniera DevOps Cloud")).title_score == 1
    assert estimate_ats(job(), good_profile(experience="")).format_score < 1


def test_the_uploaded_cv_is_read_when_it_is_text_word_or_opendocument(tmp_path):
    text = tmp_path / "cv.txt"
    text.write_text("Experiencia con Terraform y Kubernetes en producción", encoding="utf-8")
    assert "Kubernetes" in uploaded_cv_text(Profile(name="p", cv_file=str(text)))
    docx = tmp_path / "cv.docx"
    with zipfile.ZipFile(docx, "w") as archive:
        archive.writestr("word/document.xml", "<w:document><w:p><w:r><w:t>Terraform &amp; Helm</w:t></w:r></w:p></w:document>")
    assert "Terraform & Helm" in uploaded_cv_text(Profile(name="p", cv_file=str(docx)))
    odt = tmp_path / "cv.odt"
    with zipfile.ZipFile(odt, "w") as archive:
        archive.writestr("content.xml", "<office:text><text:p>Ansible</text:p></office:text>")
    assert "Ansible" in uploaded_cv_text(Profile(name="p", cv_file=str(odt)))
    for unreadable in (tmp_path / "falta.pdf", tmp_path / "cv.pdf"):
        unreadable.touch()
        assert uploaded_cv_text(Profile(name="p", cv_file=str(unreadable))) == ""
    (tmp_path / "roto.docx").write_text("no es un zip", encoding="utf-8")
    assert uploaded_cv_text(Profile(name="p", cv_file=str(tmp_path / "roto.docx"))) == ""
    assert uploaded_cv_text(Profile(name="p")) == ""


def test_the_uploaded_cv_raises_the_keyword_coverage(tmp_path):
    bare = good_profile(must=["AWS"], nice=[], experience="Soporte")
    before = estimate_ats(job(), bare)
    upload = tmp_path / "cv.txt"
    upload.write_text("Docker, Python, Bash, Terraform y Kubernetes", encoding="utf-8")
    bare.cv_file = str(upload)
    after = estimate_ats(job(), bare)
    assert after.from_upload and not before.from_upload
    assert after.keyword_score > before.keyword_score and "Docker" not in after.missing


def test_the_estimate_is_always_a_percentage_and_has_readable_labels():
    estimate = AtsEstimate(150, "high", None, None, 1.0)
    assert estimate.reliability_label and estimate.verdict
    assert 0 <= estimate_ats(job(), Profile(name="x")).percent <= 100


def test_an_offer_without_any_known_keyword_is_capped_and_never_tops_the_ranking():
    outside = job(title="Técnico Electromecánico", description="Mantenimiento de motores y cuadros eléctricos. " * 8)
    estimate = estimate_ats(outside, good_profile())
    assert estimate.no_keywords and estimate.reliability == "low" and estimate.keyword_score is None
    assert estimate.percent <= POSSIBLE - 1
    assert estimate_ats(job(), good_profile()).percent > estimate.percent           # una oferta de tu campo, por delante
    summary = job(full_description=False, description="Scrum", title="Técnico")     # una ficha resumida no es lo mismo
    assert estimate_ats(summary, good_profile()).no_keywords is False


def test_soft_skills_alone_do_not_bring_an_offer_into_scope():
    soft_only = job(title="Técnico de Mantenimiento", description="Buscamos trabajo en equipo, proactividad y liderazgo. " * 8)
    profile = good_profile(soft_must=["Trabajo en equipo"], soft_nice=["Proactividad"])
    estimate = estimate_ats(soft_only, profile)
    assert estimate.no_keywords and estimate.percent <= POSSIBLE - 1         # las blandas las cita cualquier oferta
    technical = estimate_ats(job(description=OFFER * 2 + " Trabajo en equipo."), profile)
    assert technical.no_keywords is False and technical.percent > estimate.percent
