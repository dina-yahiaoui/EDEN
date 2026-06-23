# Architecture du projet EDEN

## 1. Sources de données

L'agent EDEN reçoit différents types de données :

* Factures PDF
* Fichiers Excel
* Données logistiques
* Relevés d'énergie
* Images scannées

## 2. FastAPI

FastAPI reçoit les documents via l'endpoint :

```text
/extract
```

Ses fonctions sont :

* réception du fichier
* validation du format
* envoi vers le pipeline OCR

## 3. OCR

Les documents sont traités par :

* GPT OSS 20B
* Tesseract OCR
* Mistral OCR

Objectif :

Transformer un document en texte exploitable.

## 4. RAG

Le système RAG utilise :

* Embeddings
* Chroma ou FAISS
* Base ADEME

Il permet de retrouver automatiquement les facteurs d'émission nécessaires au calcul carbone.

## 5. LangGraph

LangGraph orchestre les différentes étapes :

* OCR
* Extraction
* Recherche des facteurs
* Calcul des émissions
* Génération du rapport

## 6. Calcul des émissions carbone

Les émissions sont calculées selon :

* Scope 1
* Scope 2
* Scope 3

et les facteurs d'émission ADEME.

## 7. Sorties

Le système produit :

* Un rapport CSRD ESRS E1
* Un dashboard de suivi
* Des automatisations via n8n

