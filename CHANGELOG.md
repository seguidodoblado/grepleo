# Changelog

## [Unreleased]

### Añadido
- Búsqueda de empleo en **InfoJobs, Indeed y LinkedIn** a través de Actors de Apify, con las ofertas repetidas entre fuentes unificadas
- **Perfiles** (varios) con requisitos imprescindibles y deseables con sinónimos, experiencia, estudios, idiomas con nivel, salario mínimo, modalidad, ubicaciones, cosas que se prefiere no encontrar y tipos de oferta
- **Evaluación de criterios** con reglas locales: cada oferta muestra qué criterios cumple (✓), cuáles no (✗) y cuáles no se pueden saber (?), con un encaje Alto, Medio o Bajo; las fichas resumidas no cuentan en contra
- **Panorama** de la muestra: requisitos más pedidos y conclusiones calculadas contando
- **Búsquedas guardadas**, última búsqueda recuperada al abrir y estado por oferta (favorita, postulada, descartada) en una base de datos local
- **Exportación** a informe HTML autocontenido y a tabla CSV
- **Control del gasto**: coste estimado antes de buscar, confirmación si es alto y tope de gasto por búsqueda en Preferencias
- Token de Apify en el llavero del sistema
- Interfaz en español e inglés con selector de idioma, tema Sistema/Claro/Oscuro e iconos del sistema
- `pytest`, `ruff`, integración continua (`ci.yml`) y despliegue (`cd.yml`: al subir una etiqueta `vX.Y.Z` ejecuta el CI y, solo si pasa, deja la release en borrador con el mismo `.deb`)
- Paquete `.deb` conforme a Debian (páginas de manual en inglés y español), `PRIVACY.md` y documentos del repositorio en español e inglés
