from grepleo.models import WorkMode
from grepleo.textutil import (
    detect_work_mode,
    language_requirements,
    mentions,
    normalize,
    required_years,
    studies_rank,
)


def test_normalize_ignores_case_and_accents():
    assert normalize("Gestión de ÁNALISIS") == "gestion de analisis"


def test_a_term_matches_whole_words_only():
    text = normalize("Experiencia con Java y JavaScript; usamos SQL")
    assert mentions(text, ["Java"]) and mentions(text, ["javascript"]) and mentions(text, ["sql"])
    assert not mentions(normalize("conocimientos de javascript"), ["Java"])
    assert mentions(normalize("Power BI avanzado"), ["PowerBI", "power bi"])
    assert mentions(normalize("stack C++ y .NET"), ["C++"]) and mentions(normalize("stack C++ y .NET"), [".NET"])
    assert not mentions(text, ["", "  "])


def test_required_years_reads_ranges_minimums_and_english():
    assert required_years("Buscamos 5-10 años de experiencia") == 5
    assert required_years("Al menos 3 años en un puesto similar") == 3
    assert required_years("más de 2 años") == 2
    assert required_years("1 año de experiencia") == 1
    assert required_years("3+ years of experience") == 3
    assert required_years("Experiencia de 4 años") == 4
    assert required_years("Sin experiencia previa") == 0
    assert required_years("Se valora experiencia") is None


def test_required_years_ignores_ages_ceilings_and_unrelated_years():
    age = ("Las personas candidatas deben ser menores de 30 años y no tener más de un año de experiencia "
           "profesional. Contrato temporal de 2 años.")
    assert required_years(age, strict=True) is None
    assert required_years("Debes tener 18 años de edad", strict=True) is None
    assert required_years("No tener más de 1 año de experiencia") is None            # un tope, no un mínimo
    assert required_years("Hasta 2 años de experiencia", strict=True) is None
    assert required_years("Somos una empresa con 20 años de historia", strict=True) is None
    assert required_years("Pedimos 3 años de trayectoria. Experiencia valorable", strict=True) is None
    assert required_years("Experiencia mínima: 4 años en proyectos de datos", strict=True) == 4
    assert required_years("Al menos 3 años") == 3                                        # campo corto: sin `strict`
    assert required_years("fundada hace 150 años") is None   # fuera de lo plausible


def test_studies_rank_picks_the_highest_level_named():
    assert studies_rank("Máster en Big Data") == 3
    assert studies_rank("Grado en Ingeniería") == 2
    assert studies_rank("Ciclo formativo de grado superior") == 1
    assert studies_rank("Bachillerato") is None


def test_language_requirements_read_the_level_near_the_language():
    found = language_requirements("Inglés C1 imprescindible; francés valorable")
    assert found == {"Inglés": "C1", "Francés": ""}
    assert language_requirements("Fluent English required")["Inglés"] == "C1"
    assert language_requirements("Nivel B2 de inglés") == {"Inglés": "B2"}
    assert language_requirements("Equipo internacional") == {}


def test_detect_work_mode():
    assert detect_work_mode("100% remoto desde España") is WorkMode.REMOTE
    assert detect_work_mode("Madrid, híbrido (2 días en oficina)") is WorkMode.HYBRID
    assert detect_work_mode("Puesto presencial") is WorkMode.ONSITE
    assert detect_work_mode("Madrid") is WorkMode.UNKNOWN


def test_studies_in_description_only_reads_sentences_about_degrees():
    from grepleo.textutil import studies_in_description
    text = ("Buscamos un ingeniero de datos con un alto grado de autonomía. "
            "Se requiere titulación universitaria o de técnico superior en informática. Ofrecemos formación continua.")
    rank, sentence = studies_in_description(text)
    assert rank == 2 and sentence.startswith("Se requiere titulación universitaria")
    assert studies_in_description("Ingeniero de datos con alto grado de autonomía.") == (None, "")
    assert studies_in_description("Requisitos: Máster en Data Science")[0] == 3
