# Architecture du projet EDEN

## 1. Sources de données

Actuellement, seules les factures PDF sont supportées (électricité, gaz,
transport, déchets). Les autres sources envisagées à terme (fichiers Excel,
relevés d'énergie multi-sources, images scannées en entrée directe) ne sont
pas implémentées.

## 2. FastAPI

FastAPI reçoit les documents via l'endpoint :

```text
POST /extract/
```

Ses fonctions sont :

* réception du fichier PDF
* validation du format (PDF uniquement)
* lancement du graphe LangGraph (§5), qui enchaîne OCR, calcul et rapport

Un second endpoint, `POST /extract/knowledge/ingest`, permet d'indexer un
document réglementaire (PDF) dans la collection Chroma `reglementation`.

## 3. OCR

Le moteur principal est :

* **GPT-4o Vision** : le PDF est converti en images (DPI 300) puis analysé
  directement par le modèle, qui renvoie un JSON structuré.

Tesseract OCR (extraction de texte brut + parsing par regex) reste présent
dans le code comme solution de repli gratuite et locale, mais n'est plus
utilisé par défaut. Mistral OCR a été évalué en benchmark
(`docs/comparaison_ocr.md`) mais n'a pas été intégré au pipeline.

## 4. RAG

Le système RAG utilise Chroma Cloud (embeddings + recherche sémantique),
avec deux collections distinctes :

* `facteurs_emission` : 12 014 lignes valides de la Base Carbone ADEME,
  utilisée en repli sémantique pour retrouver un facteur d'émission quand
  aucun des facteurs cœur (JSON direct) ne correspond.
* `reglementation` : 929 chunks (GHG Protocol, CSRD FAQ, ESRS E1), utilisée
  pour injecter du contexte réglementaire dans le rapport CSRD généré.

FAISS n'est pas utilisé.

## 5. LangGraph

Le pipeline est un vrai `StateGraph` LangGraph (`backend/app/agents/graph.py`)
à 7 nœuds, avec routage conditionnel et gestion d'erreur explicite :

* `extraction` → `verification` → (`erreur_extraction` | `calcul`)
* `calcul` → (`erreur_calcul` | `indexation`) → `generation`

`erreur_calcul` n'est pas un cul-de-sac : le pipeline continue vers
`indexation` puis `generation` même si aucun facteur d'émission n'a été
trouvé.

## 6. Calcul des émissions carbone

Les émissions sont calculées selon Scope 1, Scope 2 et Scope 3 (GHG
Protocol), à partir des facteurs d'émission ADEME (lookup direct ou RAG
sémantique, voir §4).

## 7. Sorties

Le système produit :

* Un rapport CSRD (Markdown persisté + résumé structuré JSON), avec lien
  vers ESRS E1
* Un dashboard Streamlit de suivi (extractions, indicateurs par scope,
  évolution temporelle)
* Une notification par webhook n8n (résumé envoyé par mail) en fin de
  pipeline
