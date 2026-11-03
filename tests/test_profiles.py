from grepleo.profiles import Category, Profile, parse_term


def test_parse_term_gives_the_name_and_all_synonyms():
    assert parse_term("Power BI|powerbi| PBI ") == ("Power BI", ["Power BI", "powerbi", "PBI"])
    assert parse_term("Scrum") == ("Scrum", ["Scrum"])
    assert parse_term(" | ") == ("", [])


def test_a_profile_round_trips_through_a_dict():
    profile = Profile(name="PO", headline="CRM Manager", years=8, studies="master", languages={"Inglés": "C1"},
                      must=["Scrum"], nice=["SQL"], avoid=["guardias"], salary_min=40000,
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
