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

### Semaine 3 — Du chemin complet au pipeline robuste : LangGraph, rapport, dashboard, n8n
Point de départ : le chemin OCR → extraction → calcul fonctionnait, mais "l'agent" n'était qu'un enchaînement de 3 appels de fonctions, le rapport n'était jamais vérifié bout en bout, et rien n'était visible pour un humain (pas de dashboard).

**Agent LangGraph.** Remplacé l'enchaînement séquentiel par un vrai `StateGraph` à 7 nœuds (extraction, verification, erreur_extraction, calcul, erreur_calcul, indexation, generation), avec routage conditionnel plutôt que des `if` en cascade. Décision la plus importante : séparer les deux types d'échec. Une extraction ratée (aucune donnée exploitable) est un cul-de-sac — pas de calcul ni de rapport possibles. Un calcul raté (aucun facteur trouvé) ne doit PAS l'être : la facture reste indexable dans le RAG et le rapport peut quand même se générer (en documentant l'absence de facteur), donc `erreur_calcul` continue vers indexation/génération au lieu de s'arrêter. Choisir de bloquer systématiquement aurait perdu de la donnée utile pour un problème qui n'empêche pas le reste du pipeline de tourner.

**Rapport CSRD : le bug qui ne se voyait pas.** En voulant enfin tester le rapport bout en bout, j'ai découvert qu'il n'était jamais sauvegardé sur disque — généré en mémoire, renvoyé dans la réponse API, puis perdu. Ça marchait "à l'écran" donc le problème n'avait jamais sauté aux yeux. Corrigé avec une persistance `.md` + un résumé JSON structuré à côté (même nom de fichier, extension différente). Le JSON sidecar n'est pas un luxe : le rapport est du texte libre généré par GPT-4o, pas fiable à re-parser pour en extraire des chiffres exploitables ensuite (dashboard notamment) — plus simple et plus sûr d'écrire les données structurées une seconde fois à côté, à la source, que d'essayer de les retrouver dans le Markdown après coup.

**Classification scope GHG Protocol.** Ajouté la logique 1/2/3 dans `carbon.py` (électricité = scope 2, gaz = scope 1, transport/déchets = scope 3). Testé au-delà de l'électricité (seule couverte jusque-là) en créant 3 factures fictives dédiées — gaz, transport, déchets — plutôt que d'attendre d'en trouver de vraies. Les 3 scopes sont maintenant validés avec une facture de test par cas, pas seulement en théorie dans le code.

**Dashboard Streamlit.** 4 pages : upload (appelle l'API), suivi des extractions, indicateurs CO2 par scope, évolution temporelle. Décidé de le placer dans `frontend/` et non `backend/` dès le départ — le dashboard ne doit dépendre que des fichiers écrits sur disque (résumés JSON) et de l'API HTTP, jamais importer directement le code de `backend/app/`, pour garder une frontière nette entre interface et logique métier.

**Intégration n8n.** Webhook déclenché à la fin du nœud `generation`, notification mail avec un résumé (fournisseur, CO2eq, scope, lien du rapport). Décision volontaire : l'appel webhook est best-effort — si n8n n'est pas démarré ou injoignable, c'est journalisé (log + warning) mais le pipeline ne plante jamais pour ça. Une notification ratée n'est pas une raison de perdre un rapport déjà généré.

**Robustesse.** Ajout de 10 tests pytest (offline, RAG et GPT-4o mockés) : calcul carbone (facteur JSON direct, aucun facteur trouvé, association champ/scope) et routage du graphe (a_verifier avec donnée présente, aucune donnée exploitable, erreur_calcul qui continue quand même). Corrigé aussi le fallback `invoice_date` : certaines factures n'ont pas de date d'émission distincte, seulement une période — approximée maintenant par la fin de `billing_period`, signalée via le même mécanisme `a_verifier` pour ne jamais être confondue avec une vraie date extraite. Nettoyage Git au passage : CSV ADEME désindexé (15 Mo, pas sa place dans l'historique) et suppression de fichiers morts.

**Vérification du RAG réglementaire.** Jusque-là indexé mais jamais vraiment vérifié utile. Test comparatif : rapport généré avec le contexte RAG (GHG Protocol/CSRD/ESRS E1) vs sans. Avec RAG, citation exacte d'ESRS E1-5 dans le rapport ; sans, une réponse générique sur "le climat" sans ancrage réglementaire précis. Confirme que le RAG apporte une vraie valeur au rapport, pas juste un enrichissement cosmétique.

**État actuel du projet.** Chemin complet et robuste : facture PDF → GPT-4o Vision → vérification → calcul (JSON direct ou RAG) → indexation → rapport persisté → notification n8n, avec gestion d'erreur explicite à chaque étape critique, dashboard de suivi, et tests automatisés. Documenté dans specifications_mvp.md, architecture.md et README.md, tous relus et corrigés pour coller au code réel.
**Reste à faire (mineur/cosmétique à ce stade)** : pas de pièce jointe PDF au mail n8n (résumé texte seulement), pas de conversion en MWh dans le rapport, venv encore partagé entre backend et frontend.