"""Plan de estudio: qué reforzar y dónde, a partir de lo que te falta.

Para cada habilidad que falta se ofrecen las **certificaciones oficiales** de ese tema (una tabla propia, con enlace a la
página del organismo que la otorga) y **enlaces de búsqueda** en Udemy y Coursera, en español y en inglés. No se recomiendan
cursos concretos: no se puede comprobar desde aquí que sigan existiendo, ni su precio ni su valoración, así que solo se abre
la búsqueda de esa tecnología. La tabla de certificaciones se revisó el `LAST_REVIEW` y cambia con el tiempo: conviene
comprobar en el enlace oficial que sigue vigente. Sin GTK.
"""
from __future__ import annotations

import urllib.parse
from dataclasses import dataclass

from .market import Market
from .similar import aliases, parents_of

LAST_REVIEW = "2026-11"


@dataclass(frozen=True)
class Cert:
    name: str
    issuer: str
    url: str


AWS, MS, GCP = "AWS", "Microsoft", "Google Cloud"
LF, HC = "Linux Foundation / CNCF", "HashiCorp"

# habilidad (con sus sinónimos) -> certificaciones oficiales relacionadas
CERTIFICATIONS: dict[str, tuple[Cert, ...]] = {
    "AWS|amazon web services": (
        Cert("AWS Certified Cloud Practitioner", AWS, "https://aws.amazon.com/certification/certified-cloud-practitioner/"),
        Cert("AWS Certified Solutions Architect – Associate", AWS,
             "https://aws.amazon.com/certification/certified-solutions-architect-associate/"),
        Cert("AWS Certified Developer – Associate", AWS, "https://aws.amazon.com/certification/certified-developer-associate/"),
        Cert("AWS Certified DevOps Engineer – Professional", AWS,
             "https://aws.amazon.com/certification/certified-devops-engineer-professional/")),
    "Azure|microsoft azure": (
        Cert("Azure Fundamentals (AZ-900)", MS, "https://learn.microsoft.com/credentials/certifications/azure-fundamentals/"),
        Cert("Azure Administrator Associate (AZ-104)", MS,
             "https://learn.microsoft.com/credentials/certifications/azure-administrator/"),
        Cert("DevOps Engineer Expert (AZ-400)", MS, "https://learn.microsoft.com/credentials/certifications/devops-engineer/")),
    "Azure DevOps": (
        Cert("DevOps Engineer Expert (AZ-400)", MS, "https://learn.microsoft.com/credentials/certifications/devops-engineer/"),),
    "GCP|google cloud": (
        Cert("Associate Cloud Engineer", GCP, "https://cloud.google.com/learn/certification/cloud-engineer"),
        Cert("Professional Cloud DevOps Engineer", GCP, "https://cloud.google.com/learn/certification/cloud-devops-engineer")),
    "Terraform": (
        Cert("HashiCorp Certified: Terraform Associate", HC, "https://developer.hashicorp.com/certifications/infrastructure-automation"),),
    "Vault|hashicorp vault": (
        Cert("HashiCorp Certified: Vault Associate", HC, "https://developer.hashicorp.com/certifications/security-automation"),),
    "Kubernetes|k8s": (
        Cert("Kubernetes and Cloud Native Associate (KCNA)", LF,
             "https://training.linuxfoundation.org/certification/kubernetes-cloud-native-associate/"),
        Cert("Certified Kubernetes Administrator (CKA)", LF,
             "https://training.linuxfoundation.org/certification/certified-kubernetes-administrator-cka/"),
        Cert("Certified Kubernetes Application Developer (CKAD)", LF,
             "https://training.linuxfoundation.org/certification/certified-kubernetes-application-developer-ckad/")),
    "OpenShift": (
        Cert("Red Hat Certified Specialist in OpenShift Administration", "Red Hat",
             "https://www.redhat.com/en/services/certification/rhcs-paas"),),
    "Prometheus": (
        Cert("Prometheus Certified Associate (PCA)", LF,
             "https://training.linuxfoundation.org/certification/prometheus-certified-associate/"),),
    "Linux|gnu/linux": (
        Cert("LFCS – Linux Foundation Certified Sysadmin", LF,
             "https://training.linuxfoundation.org/certification/linux-foundation-certified-sysadmin-lfcs/"),
        Cert("LPIC-1", "Linux Professional Institute", "https://www.lpi.org/our-certifications/lpic-1-overview/"),
        Cert("Red Hat Certified System Administrator (RHCSA)", "Red Hat",
             "https://www.redhat.com/en/services/certification/rhcsa"),
        Cert("CompTIA Linux+", "CompTIA", "https://www.comptia.org/certifications/linux")),
    "Redes|networking|DNS|VPN": (
        Cert("CompTIA Network+", "CompTIA", "https://www.comptia.org/certifications/network"),
        Cert("Cisco CCNA", "Cisco", "https://www.cisco.com/site/us/en/learn/training-certifications/certifications/enterprise/ccna/index.html")),
    "Ansible": (
        Cert("Red Hat Certified Engineer (RHCE)", "Red Hat", "https://www.redhat.com/en/services/certification/rhce"),),
    "Python": (
        Cert("PCEP / PCAP – Certified Python Programmer", "Python Institute", "https://pythoninstitute.org/"),),
    "Java": (
        Cert("Oracle Certified Professional: Java SE", "Oracle", "https://education.oracle.com/java"),),
    "SQL|PostgreSQL|MySQL|Oracle": (
        Cert("Azure Data Fundamentals (DP-900)", MS,
             "https://learn.microsoft.com/credentials/certifications/azure-data-fundamentals/"),),
    "Scrum|Kanban|Agile": (
        Cert("Professional Scrum Master (PSM I)", "Scrum.org", "https://www.scrum.org/assessments/professional-scrum-master-i-certification"),
        Cert("PMI Agile Certified Practitioner (PMI-ACP)", "PMI", "https://www.pmi.org/certifications/agile-acp")),
    "ITIL": (
        Cert("ITIL 4 Foundation", "PeopleCert", "https://www.peoplecert.org/"),),
    "DevSecOps|IAM|Hardening|SIEM": (
        Cert("CompTIA Security+", "CompTIA", "https://www.comptia.org/certifications/security"),
        Cert("Certified in Cybersecurity (CC)", "ISC2", "https://www.isc2.org/certifications/cc")),
    "Splunk": (
        Cert("Splunk Core Certified User", "Splunk", "https://www.splunk.com/en_us/training/certification.html"),),
    "ELK|elasticsearch": (
        Cert("Elastic Certified Engineer", "Elastic", "https://www.elastic.co/training/certification"),),
    "GitHub|GitHub Actions": (
        Cert("GitHub Certifications (Actions, Foundations…)", "GitHub", "https://resources.github.com/learn/certifications/"),),
    "Testing|QA|ISTQB": (
        Cert("ISTQB Certified Tester – Foundation Level", "ISTQB", "https://www.istqb.org/certifications/certified-tester-foundation-level"),),
    "IA|inteligencia artificial|AI|machine learning|LLM|IA generativa": (
        Cert("Azure AI Fundamentals (AI-900)", MS, "https://learn.microsoft.com/credentials/certifications/azure-ai-fundamentals/"),
        Cert("AWS Certified AI Practitioner", AWS, "https://aws.amazon.com/certification/certified-ai-practitioner/")),
    "Snowflake": (
        Cert("SnowPro Core", "Snowflake", "https://www.snowflake.com/certifications/"),),
}
_LOOKUP = tuple((aliases(spec), certs) for spec, certs in CERTIFICATIONS.items())


def certifications_for(name: str) -> list[Cert]:
    """Las certificaciones oficiales de un tema: las de la habilidad o, si es un servicio de una plataforma (EC2, S3…),
    las de esa plataforma. Sin repetir."""
    names = aliases(name)
    wanted = [names, *parents_of(names)]
    found: list[Cert] = []
    for keys, certs in _LOOKUP:
        if any(keys & candidate for candidate in wanted):
            found.extend(cert for cert in certs if cert not in found)
    return found


def course_links(name: str) -> dict[str, str]:
    """Búsquedas del tema en Udemy y Coursera, en español y en inglés (se abren en el navegador)."""
    query = urllib.parse.quote_plus(name)
    return {
        "Udemy · ES": f"https://www.udemy.com/courses/search/?q={query}&lang=es",
        "Udemy · EN": f"https://www.udemy.com/courses/search/?q={query}&lang=en",
        "Coursera · ES": f"https://www.coursera.org/search?query={query}&language=Spanish",
        "Coursera · EN": f"https://www.coursera.org/search?query={query}&language=English",
    }


@dataclass
class StudyItem:
    name: str
    radar: str
    level: float          # tu nivel
    demand: float         # lo que piden de media las ofertas que lo piden
    share: float          # qué parte de las ofertas lo piden
    priority: float       # share × (demand − nivel): lo que más rinde estudiar primero


def study_plan(market: Market, limit: int = 12) -> list[StudyItem]:
    """Lo que más conviene reforzar según el mapa del mercado: los ejes de tus radares por tema donde lo que piden las
    ofertas supera tu nivel, ordenados por cuántas lo piden y cuánta distancia hay."""
    items = []
    for radar in market.radars[1:]:   # el primero es el general, que no son habilidades sueltas
        weights = radar.weights or [1.0] * len(radar.labels)
        for label, level, demand, share in zip(radar.labels, radar.levels, radar.demand, weights, strict=True):
            if demand and demand > level and share > 0:
                items.append(StudyItem(label, radar.title, level, demand, share, share * (demand - level)))
    items.sort(key=lambda item: -item.priority)
    return items[:limit]
