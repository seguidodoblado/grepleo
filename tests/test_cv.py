from grepleo.cv import markdown_to_html, offer_markdown, profile_markdown
from grepleo.matching import evaluate
from grepleo.models import Job, WorkMode
from grepleo.profiles import Profile


def make_profile():
    return Profile(
        name="DevOps", full_name="Ana Pérez", email="ana@example.org", phone="600 000 000", links="github.com/ana",
        headline="DevOps junior", years=2, studies="degree", education="Grado en Informática, UPM",
        languages={"Inglés": "B2"}, must=["AWS", "Docker|docker"], nice=["Terraform"], soft_must=["Trabajo en equipo"],
        experience="**SRE junior** · ACME · 2023-2025\n- Automaticé despliegues con GitHub Actions")


def test_the_base_cv_is_built_from_the_profile_with_standard_sections():
    markdown = profile_markdown(make_profile())
    assert markdown.startswith("# Ana Pérez\nana@example.org · 600 000 000\ngithub.com/ana")
    for section in ("## Resumen", "## Experiencia profesional", "## Formación", "## Idiomas",
                    "## Habilidades técnicas", "## Habilidades blandas"):
        assert section in markdown
    assert "DevOps junior. 2 años de experiencia" in markdown and "- Inglés (B2)" in markdown
    assert "AWS, Docker, Terraform" in markdown and "Trabajo en equipo" in markdown
    assert "Grado universitario" in markdown and "Grado en Informática, UPM" in markdown
    assert "Automaticé despliegues" in markdown


def test_an_empty_profile_gives_only_the_name_and_no_empty_sections():
    markdown = profile_markdown(Profile(name="Vacío"))
    assert markdown == "# Vacío\n"


def test_the_offer_text_carries_the_description_and_how_the_profile_fits():
    job = Job(key="x:1", source="x", title="DevOps Engineer", company="ACME", location="Madrid",
              work_mode=WorkMode.HYBRID, url="https://example.org/1", posted="2026-11-04",
              description="Buscamos experiencia con AWS y Kubernetes. Trabajo en equipo. " * 4, full_description=True)
    profile = make_profile()
    profile.must = ["AWS", "Kubernetes"]
    text = offer_markdown(job, evaluate(job, profile))
    assert text.startswith("# DevOps Engineer\nACME · Madrid · Híbrido")
    assert "https://example.org/1" in text and "## Descripción" in text
    assert "## Encaje con mi perfil (evaluación local)" in text and "### Habilidades técnicas" in text
    assert "- ✓ AWS" in text and "- ✓ Kubernetes" in text and "Condiciones" in text


def test_markdown_becomes_escaped_printable_html():
    page = markdown_to_html("# Ana <b>\n\n## Experiencia\n**SRE** y *más*\n- uno\n- dos & tres\n\nTexto", "CV")
    assert "<title>CV</title>" in page and "<h1>Ana &lt;b&gt;</h1>" in page and "<h2>Experiencia</h2>" in page
    assert "<strong>SRE</strong> y <em>más</em>" in page
    assert "<ul><li>uno</li><li>dos &amp; tres</li></ul>" in page and "<p>Texto</p>" in page
    assert "<script" not in markdown_to_html("<script>alert(1)</script>")


def test_several_links_go_on_one_line_separated_by_dots_and_old_comma_lists_still_work():
    from grepleo.profiles import link_list
    profile = Profile(name="p", full_name="Ana", links="linkedin.com/in/ana\n\n  github.com/ana  \nana.dev")
    assert profile_markdown(profile).splitlines()[1] == "linkedin.com/in/ana · github.com/ana · ana.dev"
    assert link_list("a.com, b.com ,, c.com\nd.com") == ["a.com", "b.com", "c.com", "d.com"]
    old = Profile(name="p", full_name="Ana", links="linkedin.com/in/ana, github.com/ana")     # una línea de antes
    assert profile_markdown(old).splitlines()[1] == "linkedin.com/in/ana · github.com/ana"
    assert link_list("") == []


def test_the_offer_file_carries_the_ats_estimate_and_the_keywords_the_cv_does_not_cite():
    from grepleo.ats import estimate_ats
    job = Job(key="x:1", source="x", title="DevOps", description="Requisitos:\n- AWS, Docker y Kubernetes\n" * 4,
              full_description=True)
    profile = make_profile()
    profile.must = ["AWS"]
    text = offer_markdown(job, evaluate(job, profile), estimate_ats(job, profile))
    assert "## Estimación ATS de mi CV base" in text and "Compatibilidad estimada:" in text
    assert "Palabras clave de la oferta que mi CV base no cita" in text and "Docker" in text and "Kubernetes" in text
    assert "Estimación ATS" not in offer_markdown(job, evaluate(job, profile))        # sin estimación no hay sección
