from grepleo.profiles import Category, Profile, parse_term


def test_parse_term_gives_the_name_and_all_synonyms():
    assert parse_term("Power BI|powerbi| PBI ") == ("Power BI", ["Power BI", "powerbi", "PBI"])
    assert parse_term("Scrum") == ("Scrum", ["Scrum"])
    assert parse_term(" | ") == ("", [])


def test_a_profile_round_trips_through_a_dict():
    profile = Profile(name="PO", headline="CRM Manager", years=8, studies="master", languages={"Inglés": "C1"},
                      must=["Scrum"], nice=["SQL"], soft_must=["Liderazgo"],
                      soft_nice=["Comunicación|communication"], avoid=["guardias"], salary_min=40000,
                      work_modes=["remote", "hybrid"], locations=["Madrid"], notes="texto",
                      categories=[Category("Data PO", ["data", "datos"])])
    assert Profile.from_dict(profile.to_dict()) == profile


def test_from_dict_tolerates_missing_or_wrong_fields():
    profile = Profile.from_dict({"name": " X ", "years": "ocho", "studies": "phd", "must": "no es lista",
                                 "work_modes": ["remote", "volando"], "languages": [1],
                                 "categories": [{"name": ""}, {"name": "A", "keywords": ["a", ""]}, 3],
                                 "salary_min": True})
    assert profile.name == "X" and profile.years == 0 and profile.studies == "" and profile.must == []
    assert profile.work_modes == ["remote"] and profile.languages == {} and profile.salary_min == 0
    assert profile.categories == [Category("A", ["a"])]
    assert profile.soft_must == [] and profile.all_must == [] and profile.all_nice == []   # un perfil antiguo no las trae


def test_all_must_and_all_nice_join_technical_and_soft_skills():
    profile = Profile(name="p", must=["Python"], nice=["AWS"], soft_must=["Liderazgo"], soft_nice=["Empatía"])
    assert profile.all_must == ["Python", "Liderazgo"] and profile.all_nice == ["AWS", "Empatía"]


def test_text_helpers_for_the_profile_editor():
    from grepleo.profiles import (
        format_categories,
        format_languages,
        parse_categories,
        parse_languages,
        split_commas,
        split_lines,
    )
    assert split_lines("  uno \n\n dos  \n") == ["uno", "dos"] and split_commas(" a, ,b ,") == ["a", "b"]
    languages = parse_languages("Inglés C1, Francés b1, Alemán")
    assert languages == {"Inglés": "C1", "Francés": "B1", "Alemán": ""}
    assert format_languages(languages) == "Inglés C1, Francés B1, Alemán"
    assert parse_languages("") == {} and parse_languages("C1") == {"C1": ""}
    categories = parse_categories("Data PO: data, datos\nCRM\n: sin nombre\n")
    assert [(c.name, c.keywords) for c in categories] == [("Data PO", ["data", "datos"]), ("CRM", ["CRM"])]
    assert parse_categories(format_categories(categories)) == categories


def test_cv_fields_round_trip_and_old_profiles_do_not_have_them():
    profile = Profile(name="p", full_name="Ana", email="a@b.c", phone="1", links="gh", experience="x", education="y",
                      cv_file="/tmp/cv.pdf")
    assert Profile.from_dict(profile.to_dict()) == profile
    old = Profile.from_dict({"name": "viejo"})
    assert old.full_name == "" and old.cv_file == "" and old.experience == ""


def test_networks_round_trip_and_old_profiles_have_none():
    profile = Profile(name="p", networks={"github": "github.com/ana", "bluesky": "bsky.app/profile/ana.dev"})
    assert Profile.from_dict(profile.to_dict()) == profile
    assert Profile.from_dict({"name": "viejo", "links": "ana.dev"}).networks == {}
    odd = Profile.from_dict({"name": "x", "networks": {"github": "  github.com/a ", "web": "", "x": 5}})
    assert odd.networks == {"github": "github.com/a", "x": "5"}
    assert Profile.from_dict({"name": "y", "networks": [1]}).networks == {}


def test_a_level_written_without_a_language_is_detected():
    from grepleo.profiles import bare_levels, is_level, parse_languages
    assert is_level("A2") and is_level("c1") and not is_level("Inglés") and not is_level("A3") and not is_level("A")
    assert bare_levels("A2") == ["A2"] and bare_levels("Inglés B2, c1 , Francés") == ["c1"]
    assert bare_levels("Inglés A2, Francés B1") == [] and bare_levels("") == []
    assert parse_languages("A2") == {"A2": ""}            # lo que acababa guardándose: un idioma llamado «A2»
