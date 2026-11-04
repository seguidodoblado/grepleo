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


def test_a_flattened_text_is_split_into_paragraphs_headings_and_bullets():
    flat = ("We are a global company that builds things for clients everywhere in the world and keeps growing.Join us "
            "to grow with a caring team that values learning every day of the year in many countries around the globe "
            "and beyond.What you'll do: Design and maintain pipelinesBuild and deploy cloud-native appsDevelop "
            "infrastructure as code with TerraformCreate automation scripts in PythonMonitor systems and respond "
            "to incidents in productionSummaryWe use JavaScript, DevOps practices and PostgreSQL every single day "
            "of the week, and we love it so very much.")
    result = kinds(structure_description(flat))
    assert result[0][0] == PARAGRAPH and result[1][0] == PARAGRAPH        # «world…growing.Join us»: dos párrafos
    assert (HEADING, "What you'll do") in result
    bullets = [text for kind, text in result if kind == BULLET]
    assert "Build and deploy cloud-native apps" in bullets and "Create automation scripts in Python" in bullets
    assert any(text.startswith("Design and maintain pipelines") for text in bullets)
    assert any("JavaScript, DevOps practices and PostgreSQL" in text for _kind, text in result)   # no se parte
    assert (HEADING, "Summary") in result


def test_short_lines_without_a_final_stop_are_list_items_and_titles_open_a_section():
    text = "Intro de la empresa en una frase larga que acaba bien.\nFunciones principales\nAdministrar servidores Linux en producción todos los días\nAutomatizar despliegues con Ansible y Terraform\nGestionar copias de seguridad y su restauración"
    assert kinds(structure_description(text)) == [
        (PARAGRAPH, "Intro de la empresa en una frase larga que acaba bien."), (HEADING, "Funciones principales"),
        (BULLET, "Administrar servidores Linux en producción todos los días"),
        (BULLET, "Automatizar despliegues con Ansible y Terraform"),
        (BULLET, "Gestionar copias de seguridad y su restauración")]
