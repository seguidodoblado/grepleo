"""Panorama de una muestra de ofertas: qué requisitos se repiten y qué se puede concluir, sin GTK ni red.

Solo cuentan las ofertas con descripción completa: en una ficha resumida un requisito que «no aparece» no
quiere decir que no se pida.
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import median

from .i18n import _, ngettext
from .models import Evaluation, Fit, Job, WorkMode
from .profiles import Profile, parse_term
from .textutil import mentions, normalize

# Requisitos habituales con sus sinónimos, para que el panorama muestre también lo que tu perfil no menciona.
DEFAULT_CATALOG: tuple[str, ...] = (
    "Scrum", "Agile|ágil|metodologías ágiles", "Kanban", "Jira", "Power BI|powerbi", "Tableau", "SQL",
    "Python", "Snowflake", "Azure", "AWS|amazon web services", "GCP|google cloud", "Databricks", "ETL",
    "Salesforce", "CRM", "Dynamics 365", "SAP", "IA|inteligencia artificial|AI|machine learning|LLM",
    "Gobierno/MDM|gobierno del dato|data governance|MDM|master data", "Big Data", "Excel", "Docker",
    "Kubernetes", "Git", "Java", "JavaScript", "TypeScript", "React", "Angular", "Spring", "Linux",
    "Inglés|English",
    # infraestructura y DevOps
    "Terraform", "Ansible", "Jenkins", "CI/CD|ci cd|integración continua", "GitHub Actions", "GitLab", "Helm",
    "Prometheus", "Grafana", "Bash", "PowerShell", "Cloud", "Redes|networking", "Windows Server", "VMware",
    "Serverless|lambda", "Microservicios|microservices", "OpenShift", "ArgoCD|argo cd", "Azure DevOps",
    "CloudFormation", "Datadog", "Splunk", "Vault|hashicorp vault", "SonarQube", "ELK|elasticsearch",
    # servicios de nube, redes y plataformas
    "IaC|infrastructure as code|infraestructura como código", "EC2", "S3", "EKS", "AKS", "GKE", "VPC", "RDS",
    "CloudWatch", "DNS", "VPN", "Active Directory|directorio activo", "ECS|fargate",
    "GitOps", "SRE|site reliability", "ITIL", "FinOps", "RabbitMQ", "Redis", "Nginx", "Vue|vue.js", "Kotlin",
    # desarrollo y datos
    ".NET|dotnet", "C#", "PHP", "Node.js|nodejs", "PostgreSQL", "MySQL", "MongoDB", "Oracle", "Kafka", "Spark",
    "Airflow", "dbt",
)


@dataclass
class RequirementCount:
    name: str
    count: int


@dataclass
class Panorama:
    total: int                 # ofertas de la muestra
    detailed: int              # con descripción completa
    requirements: list[RequirementCount]
    insights: list[str]


def _terms(profile: Profile | None) -> list[str]:
    specs = list(DEFAULT_CATALOG)
    known = {normalize(parse_term(spec)[0]) for spec in specs}
    if profile:
        for spec in (*profile.all_must, *profile.all_nice):
            name = parse_term(spec)[0]
            if name and normalize(name) not in known:
                specs.append(spec)
                known.add(normalize(name))
    return specs


def count_requirements(jobs: list[Job], profile: Profile | None = None) -> list[RequirementCount]:
    """Cuántas ofertas con detalle citan cada requisito; ordenado de más a menos citado."""
    texts = [normalize(job.text) for job in jobs if job.full_description]
    counts = []
    for spec in _terms(profile):
        name, names = parse_term(spec)
        counts.append(RequirementCount(name, sum(1 for text in texts if mentions(text, names))))
    return sorted(counts, key=lambda item: (-item.count, normalize(item.name)))


def _annual_salaries(jobs: list[Job]) -> list[float]:
    return [job.salary_max if job.salary_max is not None else job.salary_min
            for job in jobs if job.salary_max is not None or job.salary_min is not None]


def build_panorama(jobs: list[Job], evaluations: dict[str, Evaluation],
                   profile: Profile | None = None) -> Panorama:
    requirements = count_requirements(jobs, profile)
    detailed = sum(1 for job in jobs if job.full_description)
    return Panorama(len(jobs), detailed, requirements, build_insights(jobs, evaluations, requirements, profile))


def build_insights(jobs: list[Job], evaluations: dict[str, Evaluation], requirements: list[RequirementCount],
                   profile: Profile | None) -> list[str]:
    """Conclusiones sencillas con plantillas: lo que se puede afirmar contando, sin interpretar los textos."""
    insights: list[str] = []
    detailed = sum(1 for job in jobs if job.full_description)
    if not jobs:
        return insights
    top = [item for item in requirements if item.count > 0][:3]
    if top and detailed:
        names = ", ".join(f"«{item.name}»" for item in top)
        insights.append(ngettext(
            "Lo más pedido: {names} (sobre {count} oferta con detalle).",
            "Lo más pedido: {names} (sobre {count} ofertas con detalle).", detailed).format(
                names=names, count=detailed))
    if profile and detailed:
        # solo lo que depende de tu perfil: un catálogo genérico daría siempre la misma frase, sin relación contigo
        unseen = []
        for spec in profile.all_nice:
            name, names = parse_term(spec)
            if name and not any(job.full_description and mentions(normalize(job.text), names) for job in jobs):
                unseen.append(name)
        if unseen:
            insights.append(_("Ninguna oferta con detalle cita tus deseables: {names}.").format(
                names=", ".join(f"«{name}»" for name in unseen[:4])))
        for spec in profile.all_must:
            name, names = parse_term(spec)
            hits = sum(1 for job in jobs if job.full_description and mentions(normalize(job.text), names))
            if name and hits * 5 < detailed:
                insights.append(_("Tu requisito «{name}» solo aparece en {hits} de {detailed} ofertas con detalle.")
                                .format(name=name, hits=hits, detailed=detailed))
    fits = [evaluations[job.key].fit for job in jobs if job.key in evaluations]
    if fits:
        insights.append(_("Encaje: {high} alto, {medium} medio y {low} bajo.").format(
            high=fits.count(Fit.HIGH), medium=fits.count(Fit.MEDIUM), low=fits.count(Fit.LOW)))
    salaries = _annual_salaries(jobs)
    if salaries:
        insights.append(_("{count} de {total} ofertas publican salario; la mediana es de {median} € al año.").format(
            count=len(salaries), total=len(jobs), median=f"{median(salaries):,.0f}".replace(",", ".")))
    remote = sum(1 for job in jobs if job.work_mode is WorkMode.REMOTE)
    if remote:
        insights.append(ngettext("{count} oferta es en remoto.", "{count} ofertas son en remoto.", remote)
                        .format(count=remote))
    summary_only = len(jobs) - detailed
    if summary_only:
        insights.append(ngettext(
            "{count} oferta es una ficha resumida: no se puede saber qué requisitos no aparecen en ella.",
            "{count} ofertas son fichas resumidas: no se puede saber qué requisitos no aparecen en ellas.",
            summary_only).format(count=summary_only))
    return insights
