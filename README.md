# EDEN

Agent IA de pilotage CSRD et décarbonation.

## Stack
- Python
- FastAPI
- LangGraph
- LangChain
- Qdrant
- Streamlit

## Objectif
Automatiser l'extraction de données environnementales et la génération de rapports carbone.

## Environnement Python
`backend/` et `frontend/` partagent actuellement un seul environnement virtuel
(`.venv/` à la racine du projet), chacun avec son propre `requirements.txt`
documentant ses dépendances réelles. Pas de séparation stricte des
environnements pour l'instant (pas le temps, pas bloquant à ce stade) — à
séparer si besoin plus tard (ex: deux venv distincts, ou un outil comme
`uv`/`poetry` par composant).