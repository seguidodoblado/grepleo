from grepleo.detail import BAD, BULLET, GOOD, HEADING, PARAGRAPH, highlight_spans, structure_description

SAMPLE = """Descripcion
Cloud Engineer Azure | Kubernetes | Hibrido

Lo que haras
Gestion y evolucion de entornos cloud en Azure.
Diseno de redes en cloud.
Automatizacion con Terraform.

Requisitos minimos:
- Azure y Kubernetes
- Linux
• Git

Ofrecemos
Un equipo estupendo con el que crecer cada dia, y un proyecto que nos importa mucho a todas
las personas que trabajamos aqui sin parar de aprender cosas nuevas"""


def kinds(blocks):
    return [(block.kind, block.text) for block in blocks]


def test_structure_finds_headings_bullets_and_paragraphs():
    result = kinds(structure_description(SAMPLE))
    assert result[0] == (HEADING, "Descripcion")
    assert result[1][0] == PARAGRAPH and "Azure" in result[1][1]
    assert (HEADING, "Lo que haras") in result
    assert (BULLET, "Gestion y evolucion de entornos cloud en Azure.") in result
    assert (BULLET, "Automatizacion con Terraform.") in result
    assert (HEADING, "Requisitos minimos") in result       # sin los dos puntos
    assert (BULLET, "Azure y Kubernetes") in result and (BULLET, "Git") in result   # sin la marca
    assert result[-2] == (HEADING, "Ofrecemos")
    assert result[-1][0] == PARAGRAPH and "\n" not in result[-1][1]                # líneas cortadas, unidas


def test_structure_handles_empty_and_plain_text():
    assert structure_description("") == [] and structure_description("  \n\n ") == []
    assert kinds(structure_description("Un texto simple sin más")) == [(PARAGRAPH, "Un texto simple sin más")]


def test_highlight_matches_synonyms_accents_and_marks_what_to_avoid():
    text = "Trabajarás con POWERBI y Scrum; se piden guardias."
    spans = highlight_spans(text, ["Power BI|powerbi", "Scrum", "Jira"], ["guardias"])
    assert [(text[a:b], kind) for a, b, kind in spans] == [("POWERBI", GOOD), ("Scrum", GOOD), ("guardias", BAD)]


def test_highlight_positions_survive_accents_and_do_not_overlap():
    text = "Gestión de datos, gestion de BI"
    spans = highlight_spans(text, ["gestión|gestion", "gestión de datos"], [])
    assert [(text[a:b]) for a, b, _kind in spans] == ["Gestión de datos", "gestion"]
    assert highlight_spans("nada de esto", ["Scrum"], []) == []
    assert highlight_spans("Java y JavaScript", ["Java"], []) == [(0, 4, GOOD)]     # no dentro de otra palabra
