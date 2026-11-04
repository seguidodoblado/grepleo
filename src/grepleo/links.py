"""Los perfiles profesionales de una persona (LinkedIn, GitHub…): las plataformas conocidas, cómo limpiar lo que se pega y
cómo salen en el currículum. Sin GTK."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .profiles import Profile, link_list


@dataclass(frozen=True)
class Platform:
    id: str                       # clave estable
    label: str                    # nombre propio de la plataforma: no se traduce
    prefix: str                   # dirección a la que se pega un nombre de usuario («github.com/»); vacío: sin atajo
    domains: tuple[str, ...]      # dominios válidos; vacío: cualquiera (la web propia)
    hint: str                     # un ejemplo del formato


PLATFORMS: tuple[Platform, ...] = (
    Platform("linkedin", "LinkedIn", "linkedin.com/in/", ("linkedin.com",), "linkedin.com/in/tu-nombre"),
    Platform("github", "GitHub", "github.com/", ("github.com",), "github.com/tu-usuario"),
    Platform("gitlab", "GitLab", "gitlab.com/", ("gitlab.com",), "gitlab.com/tu-usuario"),
    Platform("stackoverflow", "Stack Overflow", "", ("stackoverflow.com",), "stackoverflow.com/users/123/tu-nombre"),
    Platform("web", "Web", "", (), "tu-web.dev"),
    Platform("behance", "Behance", "behance.net/", ("behance.net",), "behance.net/tu-usuario"),
    Platform("medium", "Medium", "medium.com/@", ("medium.com",), "medium.com/@tu-usuario"),
    Platform("bluesky", "Bluesky", "bsky.app/profile/", ("bsky.app",), "bsky.app/profile/tu-nombre.bsky.social"),
)
PLATFORM_IDS = tuple(platform.id for platform in PLATFORMS)
_BY_ID = {platform.id: platform for platform in PLATFORMS}

DOMAIN_MISMATCH = "domain"   # el único aviso: el dominio no es el de la plataforma


def clean_url(text: str) -> str:
    """Una dirección sin esquema, sin «www.», sin parámetros ni ancla y sin barra final."""
    value = text.strip()
    value = re.sub(r"^[a-z][a-z0-9+.-]*://", "", value, flags=re.IGNORECASE)
    value = re.sub(r"^www\.", "", value, flags=re.IGNORECASE)
    value = re.split(r"[?#]", value, maxsplit=1)[0]
    return value.strip().rstrip("/")


def _host(value: str) -> str:
    return value.split("/", 1)[0].lower()


def _on_domain(value: str, platform: Platform) -> bool:
    host = _host(value)
    return any(host == domain or host.endswith("." + domain) for domain in platform.domains)


def normalize_link(platform_id: str, text: str) -> tuple[str, str]:
    """Lo que se pega en la casilla de una plataforma → (dirección limpia, aviso). Un nombre de usuario («anaperez»,
    «@anaperez») se completa con la dirección de la plataforma; una dirección entera se limpia y, si su dominio no es el
    de la plataforma, se conserva y se avisa (`DOMAIN_MISMATCH`)."""
    platform = _BY_ID[platform_id]
    value = clean_url(text)
    if not value:
        return "", ""
    if not platform.domains:
        return value, ""
    if _on_domain(value, platform):
        return value, ""
    # Un identificador de Bluesky lleva puntos («ana.bsky.social»); en las demás, un punto es parte de una dirección.
    username_like = "/" not in value and ("." not in value or platform_id == "bluesky")
    if username_like and platform.prefix:
        return platform.prefix + value.lstrip("@"), ""
    return value, DOMAIN_MISMATCH


def profile_links(profile: Profile) -> list[str]:
    """Todos los enlaces del currículum, en orden: las plataformas con su nombre («GitHub: github.com/ana») y después
    los otros enlaces tal como se escribieron."""
    labelled = [f"{platform.label}: {profile.networks[platform.id]}" for platform in PLATFORMS
                if profile.networks.get(platform.id, "").strip()]
    return [*labelled, *link_list(profile.links)]
