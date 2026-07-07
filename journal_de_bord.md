# Semaine 1 — Onboarding & veille technique

## Lundi

### Travail réalisé
- Lecture du sujet du projet EDEN
- Compréhension des objectifs du stage
- Découverte des notions :
  - CSRD
  - ESRS
  - Scope 1/2/3

### Difficultés
- Compréhension globale du vocabulaire technique

---

## Mardi

### Travail réalisé
- Début de veille technique sur :
  - RAG
  - LangChain
  - LangGraph
  - OCR
  - FastAPI
- Recherche sur les facteurs d’émission et la base ADEME

### Concepts étudiés
- embeddings
- pipeline de données
- base vectorielle

---

## Mercredi

### Travail réalisé
- Création du repository Git
- Création de la branche `develop`
- Mise en place de la structure du projet
- Création de l’environnement virtuel Python
- Initialisation du README
- Début de rédaction de la veille CSRD / ESRS E1

### Difficultés
- Compréhension de l’architecture globale du projet EDEN

---

## Jeudi

### Travail prévu
- Finalisation de la note de synthèse CSRD / ESRS E1
- Organisation des notebooks techniques
- Début des premiers tests LangChain / RAG


### Semaine 2 — 
Pipeline d'extraction : de "briques éparses" à un chemin complet
Point de départ : structure du projet en place (FastAPI, OCR, RAG, agent) mais rien ne fonctionnait bout en bout.
Ce que j'ai fait

Audit du code existant → 2 bugs trouvés avant de coder : schéma de données incohérent entre parser.py et carbon.py, facteurs d'émission codés en dur.
Nettoyage de la Base Carbone ADEME : 5 facteurs cœur en JSON direct (électricité, gaz, transport, déchets) + 12 014 lignes indexées dans Chroma en fallback sémantique. Facteur électricité choisi daté ("2024 - mix moyen") plutôt qu'une ligne non traçable, pour rester défendable en audit CSRD.
Indexé GHG Protocol, ESRS E1 et une note CSRD de la Commission dans une collection séparée pour usage futur par l'agent.

Décision clé : GPT-4o Vision avancé plus tôt que prévu
Premier test (Tesseract + regex) : 7/11 champs corrects sur 4 factures, erreurs sérieuses (mauvaise ligne kWh, mauvaise date). Confirme la fragilité déjà pointée dans mon benchmark initial. Plutôt que patcher regex indéfiniment, j'ai basculé sur GPT-4o Vision (prévu semaine 5) → 11/11 corrects, coût négligeable (~0,01$/facture).
Blocages résolus

Un null suspect sur une facture = en fait correct (donnée réellement absente, juste "estimée"). Ajout d'un champ a_verifier plutôt que deviner une valeur.
Instabilité d'une date entre appels → pas un bug du modèle mais une image trop basse résolution (DPI 200→300 a réglé le problème).

Ce que je retiens
Vérifier chaque hypothèse dans les données sources avant de la considérer acquise — plusieurs fois, ce qui semblait être "le problème" n'en était pas la vraie cause. Éviter d'ajouter de la complexité avant d'avoir écarté les causes simples.
État fin semaine 2
Chemin complet fonctionnel et tracé : facture → GPT-4o Vision → JSON structuré → facteur ADEME (direct ou RAG) → CO2eq avec source. Documenté dans specifications_mvp.md.
Reste à faire : rapport CSRD non testé bout en bout, agent encore séquentiel simple, pas de dashboard.