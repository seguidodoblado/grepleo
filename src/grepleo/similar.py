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
PARENT_FACTOR = 0.9    # cuánto cubre tener la plataforma o la base cuando se pide uno de sus servicios o derivados

SIMILAR_GROUPS: tuple[tuple[str, ...], ...] = (
    ("AWS|amazon web services", "Azure|microsoft azure", "GCP|google cloud"),                    # nubes
    ("EC2", "Azure VM|máquinas virtuales|virtual machines", "Compute Engine"),                    # máquinas virtuales
    ("S3", "Blob Storage", "Cloud Storage"),                                                       # almacenamiento de objetos
    ("RDS", "Azure SQL", "Cloud SQL", "Aurora"),                                                   # bases de datos gestionadas
    ("Serverless|lambda", "Azure Functions", "Cloud Functions", "Cloud Run"),                      # funciones sin servidor
    ("Jenkins", "GitHub Actions", "GitLab CI|GitLab", "Azure DevOps", "CircleCI", "Bamboo"),       # CI/CD
    ("ArgoCD|argo cd", "Flux|fluxcd"),                                                             # GitOps
    ("Terraform", "CloudFormation", "Pulumi", "Bicep"),                                            # infraestructura como código
    ("Ansible", "Puppet", "Chef", "SaltStack|salt"),                                               # gestión de configuración
    ("Docker", "Podman"),                                                                          # contenedores
    ("Kubernetes|k8s", "OpenShift", "EKS", "AKS", "GKE"),                                          # orquestación
    ("Helm", "Kustomize"),                                                                         # paquetes de Kubernetes
    ("Grafana", "Prometheus", "Datadog", "New Relic", "Splunk", "ELK|elasticsearch", "CloudWatch",
     "Azure Monitor"),                                                                             # observabilidad
    ("Kafka", "RabbitMQ", "SQS", "Pub/Sub|pubsub", "Service Bus"),                                 # mensajería
    ("SQL", "PostgreSQL", "MySQL", "MariaDB", "Oracle", "SQL Server"),                             # bases de datos relacionales
    ("MongoDB", "DynamoDB", "Cosmos DB", "Cassandra"),                                             # bases de datos NoSQL
    ("Redis", "Memcached"),                                                                        # cachés
    ("Nginx", "Apache", "HAProxy", "Traefik"),                                                     # servidores web y balanceadores
    ("Vault|hashicorp vault", "Secrets Manager", "Key Vault"),                                     # gestión de secretos
    ("SonarQube", "Snyk", "Trivy", "Checkmarx"),                                                   # calidad y seguridad del código
    ("Selenium", "Cypress", "Playwright"),                                                         # pruebas de interfaz
    ("Bash", "PowerShell", "Shell"),                                                               # scripting de sistemas
    ("Linux|gnu/linux", "Unix"),                                                                   # sistemas operativos
    ("GitHub", "GitLab", "Bitbucket"),                                                             # plataformas de código
    ("Jira", "Azure Boards", "Trello", "Asana"),                                                   # gestión de tareas
    ("JavaScript", "TypeScript"),                                                                  # lenguajes web
    ("React", "Angular", "Vue|vue.js"),                                                            # frameworks de interfaz
    ("Java", "C#", "Kotlin"),                                                                      # lenguajes de la misma familia
)



# quien tiene la plataforma o la base cubre casi del todo lo que se pide de ella: AWS cubre EC2, S3 o EKS
PARENTS: dict[str, tuple[str, ...]] = {
    "AWS|amazon web services": ("EC2", "S3", "EKS", "VPC", "RDS", "CloudWatch", "ECS|fargate", "Serverless|lambda",
                                "Aurora", "DynamoDB", "SQS", "CloudFormation"),
    "Azure|microsoft azure": ("AKS", "Azure Functions", "Cosmos DB", "Key Vault", "Azure Monitor", "Blob Storage",
                              "Service Bus", "Bicep"),
    "GCP|google cloud": ("GKE", "Cloud Run", "Cloud Functions", "Cloud SQL", "Pub/Sub|pubsub", "Cloud Storage"),
    "Kubernetes|k8s": ("EKS", "AKS", "GKE"),
    "Git": ("GitHub", "GitLab", "Bitbucket"),
    "SQL": ("PostgreSQL", "MySQL", "MariaDB", "SQL Server", "Oracle"),
}

# términos genéricos que cubre del todo quien tiene cualquiera de sus concreciones: «Cloud» lo cubre tener AWS
UMBRELLAS: dict[str, tuple[str, ...]] = {
    "cloud": ("AWS|amazon web services", "Azure|microsoft azure", "GCP|google cloud", "Kubernetes|k8s"),
    "iac": ("Terraform", "CloudFormation", "Pulumi", "Bicep", "Ansible"),
    "ci/cd": ("Jenkins", "GitHub Actions", "GitLab CI|GitLab", "Azure DevOps", "CircleCI", "ArgoCD|argo cd"),
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
    for parent in parents_of(spec_aliases):   # un servicio de AWS se parece a las otras nubes en general
        related.extend(member for member in similar_to(parent) if member not in related)
    return related


def umbrella_members(spec_aliases: frozenset[str]) -> list[frozenset[str]]:
    """Las concreciones de un término genérico («Cloud»): quien tiene una cubre el término entero."""
    members: list[frozenset[str]] = []
    for key, specs in UMBRELLAS.items():
        if key in spec_aliases:
            members.extend(aliases(spec) for spec in specs)
    return members


@lru_cache(maxsize=1)
def _parents() -> tuple[tuple[frozenset[str], tuple[frozenset[str], ...]], ...]:
    return tuple((aliases(parent), tuple(aliases(child) for child in children)) for parent, children in PARENTS.items())


def parents_of(spec_aliases: frozenset[str]) -> list[frozenset[str]]:
    """Los nombres de las plataformas o bases de las que forma parte lo pedido (AWS para EC2)."""
    return [parent for parent, children in _parents() if any(child & spec_aliases for child in children)]
