from grepleo.market import Market
from grepleo.radar import RadarData
from grepleo.study import CERTIFICATIONS, LAST_REVIEW, certifications_for, course_links, study_plan


def names(items):
    return [cert.name for cert in items]


def test_a_skill_has_the_official_certifications_of_its_topic_and_a_service_those_of_its_platform():
    assert "HashiCorp Certified: Terraform Associate" in names(certifications_for("Terraform"))
    assert "Certified Kubernetes Administrator (CKA)" in names(certifications_for("kubernetes"))   # sin mayúsculas
    assert "AWS Certified Solutions Architect – Associate" in names(certifications_for("EC2"))    # servicio de AWS
    assert "AWS Certified Solutions Architect – Associate" in names(certifications_for("Amazon Web Services"))
    assert certifications_for("Cobol") == []                                       # sin certificación en la tabla
    assert len(names(certifications_for("Azure DevOps"))) == len(set(names(certifications_for("Azure DevOps"))))


def test_every_certification_points_to_an_https_page_of_its_issuer_and_the_table_has_a_review_date():
    assert LAST_REVIEW[:2] == "20"
    for certs in CERTIFICATIONS.values():
        for cert in certs:
            assert cert.url.startswith("https://") and cert.name and cert.issuer


def test_course_links_search_udemy_and_coursera_in_both_languages_without_naming_courses():
    links = course_links("Infraestructura como código")
    assert list(links) == ["Udemy · ES", "Udemy · EN", "Coursera · ES", "Coursera · EN"]
    assert links["Udemy · ES"] == "https://www.udemy.com/courses/search/?q=Infraestructura+como+c%C3%B3digo&lang=es"
    assert links["Udemy · EN"].endswith("&lang=en")
    assert links["Coursera · ES"].startswith("https://www.coursera.org/search?query=") and links[
        "Coursera · ES"].endswith("language=Spanish") and links["Coursera · EN"].endswith("language=English")


def test_the_study_plan_ranks_what_more_offers_ask_for_above_your_level():
    general = RadarData("General", ["T"], [5.0], [8.0], weights=[1.0])
    cloud = RadarData("Cloud", ["AWS", "Azure", "GCP", "Alibaba"], [8.0, 2.0, 7.0, 0.0], [9.0, 8.0, 7.0, 10.0],
                      weights=[0.6, 0.5, 0.1, 0.0])
    market = Market([general, cloud], 10, 10)
    plan = study_plan(market)
    assert [item.name for item in plan] == ["Azure", "AWS"]                       # GCP ya lo cubres; Alibaba nadie lo pide
    assert plan[0].priority == 0.5 * (8 - 2) and (plan[0].level, plan[0].demand) == (2.0, 8.0)
    assert plan[0].radar == "Cloud" and study_plan(Market([], 0, 0)) == []
    assert len(study_plan(market, limit=1)) == 1
