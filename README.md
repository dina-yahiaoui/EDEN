# EDEN

Agent IA de pilotage CSRD et décarbonation. À partir d'une facture d'énergie
(électricité, gaz, transport, déchets) au format PDF, EDEN extrait les
données de consommation, calcule les émissions CO2e via les facteurs
d'émission ADEME, et génère un rapport CSRD. Le pipeline est orchestré par un
graphe LangGraph et exposé via une API FastAPI et un dashboard Streamlit.

## Stack
- Python
- FastAPI (API)
- LangGraph (orchestration du pipeline)
- LangChain (découpage et chargement de documents pour le RAG)
- OpenAI GPT-4o (extraction Vision sur facture + génération du rapport CSRD)
- Chroma Cloud (base vectorielle : facteurs ADEME, réglementation, factures indexées)
- Streamlit (dashboard de suivi)
- n8n (notification par mail via webhook en fin de pipeline)
- pytest (tests automatisés, `backend/tests/`)

## Objectif
Automatiser l'extraction de données environnementales et la génération de rapports carbone.

## Lancer le projet
Voir [DEMO.md](DEMO.md) pour l'ordre de lancement complet (Docker/n8n → API
FastAPI → dashboard Streamlit) et les factures de test recommandées.

## Documentation
- [docs/specifications_mvp.md](docs/specifications_mvp.md) : état détaillé du pipeline, périmètre couvert, limites connues.
- [docs/architecture.md](docs/architecture.md) : architecture cible du projet.

## Environnement Python
`backend/` et `frontend/` partagent actuellement un seul environnement virtuel
(`.venv/` à la racine du projet), chacun avec son propre `requirements.txt`
documentant ses dépendances réelles. Pas de séparation stricte des
environnements pour l'instant (pas le temps, pas bloquant à ce stade) — à
séparer si besoin plus tard (ex: deux venv distincts, ou un outil comme
`uv`/`poetry` par composant).