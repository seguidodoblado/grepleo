from grepleo.cv import profile_markdown
from grepleo.links import DOMAIN_MISMATCH, PLATFORM_IDS, PLATFORMS, clean_url, normalize_link, profile_links
from grepleo.profiles import Profile


def test_there_is_a_platform_for_bluesky_and_none_for_twitter():
    labels = [platform.label for platform in PLATFORMS]
    assert "Bluesky" in labels and "X" not in labels and "Twitter" not in labels
    assert PLATFORM_IDS == ("linkedin", "github", "gitlab", "stackoverflow", "web", "behance", "medium", "bluesky")


def test_a_pasted_address_is_cleaned():
    assert clean_url("  https://www.GitHub.com/ana/?tab=repos#x ") == "GitHub.com/ana"
    assert clean_url("HTTP://ana.dev/portfolio/") == "ana.dev/portfolio" and clean_url("") == ""


def test_a_username_is_completed_with_the_address_of_the_platform():
    assert normalize_link("github", "anaperez") == ("github.com/anaperez", "")
    assert normalize_link("github", "@anaperez") == ("github.com/anaperez", "")
    assert normalize_link("gitlab", "ana") == ("gitlab.com/ana", "")
    assert normalize_link("linkedin", "ana-perez") == ("linkedin.com/in/ana-perez", "")
    assert normalize_link("medium", "@ana") == ("medium.com/@ana", "")
    assert normalize_link("behance", "ana") == ("behance.net/ana", "")


def test_a_bluesky_handle_has_dots_and_is_still_a_username():
    assert normalize_link("bluesky", "ana.bsky.social") == ("bsky.app/profile/ana.bsky.social", "")
    assert normalize_link("bluesky", "@ana.dev") == ("bsky.app/profile/ana.dev", "")          # dominio propio como identificador
    assert normalize_link("bluesky", "https://bsky.app/profile/ana.bsky.social/") == \
        ("bsky.app/profile/ana.bsky.social", "")


def test_an_address_of_another_platform_is_kept_but_flagged():
    assert normalize_link("github", "gitlab.com/ana") == ("gitlab.com/ana", DOMAIN_MISMATCH)
    assert normalize_link("linkedin", "https://github.com/ana") == ("github.com/ana", DOMAIN_MISMATCH)
    assert normalize_link("stackoverflow", "ana") == ("ana", DOMAIN_MISMATCH)      # sin atajo: hace falta la dirección
    assert normalize_link("stackoverflow", "stackoverflow.com/users/1/ana") == ("stackoverflow.com/users/1/ana", "")
    assert normalize_link("github", "gist.github.com/ana") == ("gist.github.com/ana", "")   # un subdominio es del mismo sitio


def test_the_own_website_accepts_any_address_and_blanks_are_empty():
    assert normalize_link("web", "https://ana.dev/") == ("ana.dev", "")
    assert normalize_link("github", "   ") == ("", "")


def test_the_cv_lists_the_platforms_with_their_name_in_a_fixed_order_and_then_the_other_links():
    profile = Profile(name="p", full_name="Ana", networks={"github": "github.com/ana", "linkedin": "linkedin.com/in/ana",
                                                           "bluesky": "bsky.app/profile/ana.dev", "x": "ignorada"},
                      links="ana.dev\nbehance.net/ana")
    assert profile_links(profile) == ["LinkedIn: linkedin.com/in/ana", "GitHub: github.com/ana",
                                      "Bluesky: bsky.app/profile/ana.dev", "ana.dev", "behance.net/ana"]
    assert profile_markdown(profile).splitlines()[1] == ("LinkedIn: linkedin.com/in/ana · GitHub: github.com/ana · "
                                                         "Bluesky: bsky.app/profile/ana.dev · ana.dev · behance.net/ana")
    assert profile_links(Profile(name="vacío")) == []
