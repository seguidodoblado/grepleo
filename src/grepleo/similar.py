"""Herramientas parecidas entre sí: quien domina una cubre en parte lo que pide la oferta de otra.

Un reclutador que pide Azure y se encuentra a alguien con AWS y GCP suele ceder: se adapta rápido. Estos grupos se
usan para dar un crédito parcial (`SIMILAR_FACTOR`) cuando la oferta pide algo que no tienes pero sí algo del mismo
grupo. Son pocos y claros a propósito: un lenguaje como Python no cubre a otro como Java. Sin GTK.
"""
from __future__ import annotations

from functools import lru_cache

from .profiles import parse_term
from .textutil import normalize

SIMILAR_FACTOR = 0.6   # cuánto cubre lo parecido: 0,6 de lo que cubriría tener justo lo que se pide

SIMILAR_GROUPS: tuple[tuple[str, ...], ...] = (
    ("AWS|amazon web services", "Azure|microsoft azure", "GCP|google cloud"),                    # nubes
    ("Jenkins", "GitHub Actions", "GitLab CI|GitLab", "Azure DevOps", "CircleCI", "Bamboo"),       # CI/CD
    ("Terraform", "CloudFormation", "Pulumi", "Bicep"),                                            # infraestructura como código
    ("Ansible", "Puppet", "Chef", "SaltStack|salt"),                                               # gestión de configuración
    ("Docker", "Podman"),                                                                          # contenedores
    ("Kubernetes|k8s", "OpenShift"),                                                               # orquestación
    ("Grafana", "Prometheus", "Datadog", "New Relic", "Splunk", "ELK|elasticsearch"),              # observabilidad
    ("SQL", "PostgreSQL", "MySQL", "MariaDB", "Oracle", "SQL Server"),                             # bases de datos relacionales
    ("Bash", "PowerShell", "Shell"),                                                               # scripting de sistemas
    ("GitHub", "GitLab", "Bitbucket"),                                                             # plataformas de código
    ("Java", "C#", "Kotlin"),                                                                      # lenguajes de la misma familia
)


# términos genéricos que cubre del todo quien tiene cualquiera de sus concreciones: «Cloud» lo cubre tener AWS
UMBRELLAS: dict[str, tuple[str, ...]] = {
    "cloud": ("AWS|amazon web services", "Azure|microsoft azure", "GCP|google cloud", "Kubernetes|k8s"),
}


@lru_cache(maxsize=4096)
def aliases(spec: str) -> frozenset[str]:
    """Todo lo que nombra a un elemento, normalizado (sin tildes ni mayúsculas)."""
    return frozenset(normalize(name) for name in parse_term(spec)[1])


_GROUPS = tuple(tuple(aliases(spec) for spec in group) for group in SIMILAR_GROUPS)


def similar_to(spec_aliases: frozenset[str]) -> list[frozenset[str]]:
    """Los nombres de los elementos parecidos al dado (los de sus grupos, sin él mismo)."""
    related: list[frozenset[str]] = []
    for group in _GROUPS:
        if any(member & spec_aliases for member in group):
            related.extend(member for member in group if not member & spec_aliases)
    return related


def umbrella_members(spec_aliases: frozenset[str]) -> list[frozenset[str]]:
    """Las concreciones de un término genérico («Cloud»): quien tiene una cubre el término entero."""
    members: list[frozenset[str]] = []
    for key, specs in UMBRELLAS.items():
        if key in spec_aliases:
            members.extend(aliases(spec) for spec in specs)
    return members
