# Spécifications MVP — EDEN

## 1. Objectif du MVP

Le MVP couvre un chemin complet et fonctionnel : à partir d'une facture d'énergie, de gaz, de transport ou de déchets au format PDF, extraire automatiquement les données de consommation, retrouver le facteur d'émission ADEME correspondant, calculer les émissions de CO2e associées avec une source traçable, et produire un rapport CSRD persisté. L'objectif n'est pas de couvrir tous les cas d'usage du produit final (Excel, données logistiques détaillées, relevés multi-sources), mais de valider que la chaîne OCR → extraction structurée → calcul carbone → rapport fonctionne de bout en bout sur des factures réelles, avec une fiabilité mesurée plutôt que supposée.

## 2. Pipeline actuel

Le pipeline est orchestré par un graphe LangGraph (`StateGraph`, `backend/app/agents/graph.py`) à 7 nœuds, avec routage conditionnel et gestion d'erreur explicite — ce n'est plus un simple enchaînement séquentiel de fonctions.

1. **`extraction`** : la facture PDF, reçue via `POST /extract/` (`backend/app/api/extract.py`), est convertie en images PNG (`pdf2image`, DPI 300) puis envoyée à GPT-4o Vision (`backend/app/ocr/gpt4o.py`, `temperature=0`) avec un prompt structuré qui renvoie directement un JSON harmonisé (`electricity_kwh, gas_m3, waste_tons, logistics_km, invoice_number, invoice_date, billing_period, supplier, amount_total, a_verifier, raison_verification`).
2. **`verification`** : contrôle qu'au moins un champ de consommation est exploitable, et propage `a_verifier`/`raison_verification` jusqu'au state final. Route vers `calcul` si ok, vers `erreur_extraction` sinon.
3. **`erreur_extraction`** (route de sortie) : arrête le pipeline si aucune donnée de consommation n'a pu être extraite — pas de calcul ni de rapport possibles dans ce cas.
4. **`calcul`** : `carbon.py` (`backend/app/services/carbon.py`) calcule les émissions pour chaque champ de consommation présent, en lookup direct dans `facteurs_clean.json` si un facteur cœur correspond, sinon en recherche sémantique dans Chroma. Route vers `indexation` si au moins un facteur a été trouvé, vers `erreur_calcul` sinon.
5. **`erreur_calcul`** : marque l'échec du calcul mais ne bloque pas le pipeline — enchaîne quand même vers `indexation`.
6. **`indexation`** : indexe la facture dans Chroma (collection `energy-invoices`).
7. **`generation`** : récupère le contexte réglementaire (RAG), génère le rapport CSRD via GPT-4o (`report.py`), le persiste sur disque (`.md` + résumé structuré `.json` dans `backend/data/reports/`), puis notifie un webhook n8n en best-effort.

`tesseract.py` + `parser.py` (OCR classique + regex) restent dans le code mais ne sont plus utilisés par défaut (voir §5).

## 3. Périmètre couvert

Les 3 scopes du GHG Protocol sont couverts et validés avec des factures de test réelles (électricité, gaz, transport et déchets créés spécifiquement pour ce test) :

- **Électricité** (scope 2) : `electricity_france`, mix moyen France continentale 2024, 0,0519 kgCO2e/kWh.
- **Gaz naturel** (scope 1) : `gas_naturel`, mix moyen, 2,32 kgCO2e/m3.
- **Transport routier** (scope 3), 2 catégories : `transport_routier_poids_lourd` (rigide 12-20t diesel, 0,169 kgCO2e/t.km) et `transport_routier_utilitaire_leger` (VUL diesel, 0,842 kgCO2e/t.km).
- **Déchets d'activité économique non dangereux** (scope 3) : `dechets_dae` (DIB, ligne "Impacts" hors émissions évitées, 87,0 kgCO2e/tonne).

Ces 5 facteurs cœur sont dans `backend/knowledge/ademe/facteurs_clean.json`, dérivés de `base_carbone.csv` (script `clean_ademe.py`). En complément, la collection Chroma `facteurs_emission` contient les **12 014 lignes valides** (statut "Valide générique/spécifique") de la Base Carbone complète, tous secteurs confondus, utilisée en repli sémantique quand aucun des 5 facteurs cœur ne correspond.

Une seconde collection Chroma, `reglementation`, indexe GHG Protocol, CSRD FAQ et ESRS E1 (929 chunks) pour la recherche de contexte réglementaire injecté dans le rapport CSRD généré à l'étape `generation`.

## 4. Ce qui est maintenant couvert

- **Dashboard Streamlit** (`frontend/app.py`) : upload d'une facture (appelle l'API FastAPI), suivi des extractions déjà traitées, indicateurs CO2e par scope GHG Protocol (graphique + tableau), évolution temporelle des émissions par date de facture. Les pages de suivi lisent directement les résumés JSON écrits dans `backend/data/reports/`, sans dépendre de l'API.
- **Génération et persistance du rapport CSRD** : `report.py` est appelé par le nœud `generation` du graphe, testé des dizaines de fois sur des factures réelles et de test. Le rapport est sauvegardé en `.md`, accompagné d'un résumé structuré `.json` au même chemin (`backend/data/reports/rapport_csrd_<numero>_<timestamp>.{md,json}`).
- **Webhook n8n** : notification best-effort en fin de pipeline (nœud `generation`) vers `http://localhost:5678/webhook/rapport-csrd`, avec un résumé texte (fournisseur, CO2eq total, scope(s), chemin du rapport, numéro de facture) envoyé par mail via le workflow n8n. Une panne du webhook est journalisée mais ne fait jamais échouer le pipeline.
- **Tests automatisés** (`backend/tests/`, 10 tests, offline) : `test_carbon.py` couvre le calcul carbone (facteur JSON direct, aucun facteur trouvé, association champ → scope, champ absent) ; `test_graph.py` couvre le routage du graphe LangGraph (`a_verifier=true` avec donnée présente → continue vers calcul, aucune donnée exploitable → `erreur_extraction`, `erreur_calcul` → continue quand même vers indexation/génération).

## 5. Ce qui n'est PAS couvert

- **Formats d'entrée** : seul le PDF de facture est géré. Les fichiers Excel et relevés d'énergie mentionnés dans `docs/architecture.md` comme sources cibles ne sont pas implémentés.
- **Transport/déchets au-delà des catégories retenues** : les 49 catégories transport et 31 catégories déchets identifiées dans la Base Carbone n'ont pas toutes été triées ; seules celles jugées pertinentes ont été ajoutées aux facteurs cœur (voir §3).
- **Validation humaine du flag `a_verifier`** : le champ existe, est renseigné par le modèle et affiché dans le dashboard, mais rien dans le pipeline ne bloque ou ne met en file d'attente une facture marquée `a_verifier` — c'est un signal, pas un contrôle.
- **`logistics_km`** : jamais résolu par lookup direct, toujours par le RAG (voir §6).

## 6. RAG à deux niveaux

Le calcul carbone (`resolve_factor()` dans `carbon.py`) distingue deux sources de facteur, dans cet ordre :

1. **Lookup JSON direct** (`facteurs_clean.json`, 5 facteurs cœur) : pour `electricity_kwh`, `gas_m3` et `waste_tons`, la valeur est fixée une fois pour toutes, vérifiée manuellement, traçable par une clé stable (`electricity_france`, `gas_naturel`, `dechets_dae`, `transport_routier_*`). Utilisé en priorité chaque fois qu'une correspondance directe existe.
2. **Fallback Chroma sémantique** (collection `facteurs_emission`, 12 014 lignes ADEME) : utilisé quand aucun facteur cœur ne correspond au champ. La recherche filtre les résultats par compatibilité d'unité (rejette par exemple un facteur en `kgCO2e/t.km` pour une donnée en km seul) et lit la valeur dans les métadonnées du résultat, jamais dans le texte généré, pour garantir l'exactitude du chiffre.

Une collection Chroma distincte, `reglementation` (929 chunks, GHG Protocol + CSRD FAQ + ESRS E1), sert uniquement à la génération du rapport (`retrieve_context()`), pas au calcul carbone.

## 7. Mécanismes de fiabilité

- **`a_verifier` / `raison_verification`** : signale deux cas distincts, tous deux détectés à l'extraction (`gpt4o.py`) :
  1. **Estimation détectée** : la seule valeur de consommation trouvée sur la facture était qualifiée de référence/prévisionnelle/estimée (ex : facture de mensualisation) — la valeur est alors écartée plutôt que retenue à tort comme consommation réelle.
  2. **Date de facture absente** : quand aucune date d'émission distincte n'est présente sur le document, `invoice_date` est approximée par la fin de `billing_period`, et ce fallback est signalé via le même mécanisme pour ne jamais être confondu avec une vraie date extraite.
- **Gestion d'erreur du graphe** : deux routes d'échec distinctes et de comportement différent.
  - `erreur_extraction` : cul-de-sac — si aucune donnée de consommation n'est exploitable, le pipeline s'arrête (pas de calcul ni de rapport possibles).
  - `erreur_calcul` : non bloquant — si aucun facteur d'émission n'est trouvé (ni JSON ni RAG), le statut est marqué en échec mais le pipeline continue vers `indexation` puis `generation`, pour ne pas perdre l'indexation RAG ni le rapport (qui documente alors l'absence de facteur).

## 8. Choix techniques justifiés

**GPT-4o Vision plutôt que Tesseract+regex, par défaut.** Testé sur 4 factures réelles (1 Iberdrola, 3 TotalEnergies) sur 3 champs critiques (consommation, date de facture, montant total) : GPT-4o Vision obtient 11/11 corrects après itérations (prompt + DPI), contre 7/11 pour Tesseract+regex. Le regex se trompait de façon récurrente mais différente selon le fournisseur : ligne de calcul de taxe confondue avec la consommation totale, date de mention légale confondue avec la date de facture, valeur tarifaire partielle confondue avec le total, montant en prose non reconnu. GPT-4o Vision, avec un prompt explicite sur ces pièges récurrents, généralise mieux d'un fournisseur à l'autre sans code spécifique par format de facture. Le coût reste faible (≈0,01 $/facture). Tesseract+regex est conservé dans le code comme solution de repli gratuite et locale, mais n'est plus le chemin par défaut.

**Lookup JSON direct + repli RAG, plutôt que RAG seul.** Pour les 4 types de consommation les plus fréquents, le facteur exact est fixé dans `facteurs_clean.json` : la valeur utilisée est toujours la même, choisie et vérifiée une fois, traçable par une clé stable. Une recherche sémantique seule sur 12 014 lignes pourrait renvoyer un facteur différent d'un appel à l'autre, ou dimensionnellement incompatible (ex : confondre un facteur en kgCO2e/t.km avec une donnée en km — ce cas s'est produit en test et a été corrigé par un filtre de compatibilité d'unité). Le RAG reste utile en repli pour les cas hors des 5 facteurs cœur.

**LangGraph avec routes d'erreur explicites, plutôt qu'un enchaînement de fonctions.** Séparer `erreur_extraction` (bloquant) et `erreur_calcul` (non bloquant) permet de préserver l'indexation RAG et le rapport même quand le calcul carbone échoue, plutôt que de tout arrêter à la première erreur.

## 9. Limites connues actuelles

- **Pas de conversion en MWh** : le rapport CSRD affiche les consommations dans l'unité brute extraite (kWh, m3, tonnes, km), sans conversion vers des unités plus adaptées à un reporting CSRD (MWh notamment pour l'électricité/le gaz).
- **Pas de pièce jointe PDF au mail** : le webhook n8n envoie un résumé texte (fournisseur, CO2eq, scope, chemin du rapport) mais pas le rapport `.md` en pièce jointe — pour le lire, il faut ouvrir le chemin indiqué sur le disque.
- **Venv partagé backend/frontend** : un seul environnement virtuel Python à la racine du projet sert à la fois à l'API FastAPI (`backend/requirements.txt`) et au dashboard Streamlit (`frontend/requirements.txt`), malgré des `requirements.txt` séparés — pas d'isolation entre les dépendances des deux services.
- **`logistics_km` toujours résolu par le RAG** : les facteurs transport du JSON cœur sont exprimés en kgCO2e/t.km (nécessitent un tonnage), pas en kgCO2e/km seul ; une distance seule ne peut donc jamais matcher un lookup direct — c'est une limitation structurelle d'unité, pas un oubli d'implémentation.
- **Dépendance à la qualité d'image (DPI)** : à DPI 200 (défaut de `pdf2image`), l'extraction s'est montrée instable d'un appel à l'autre. Passé à DPI 300, la même facture donne des résultats stables sur plusieurs sessions séparées. Le comportement sur des scans de moins bonne qualité n'a pas été testé.
- **Non-déterminisme résiduel** : `temperature=0` réduit mais ne garantit pas une sortie identique à chaque appel (comportement documenté du modèle). Aucun mécanisme de vote/re-vérification n'est en place.
- **Corruption d'encodage du CSV source** : `base_carbone.csv` contient une corruption irréversible des caractères accentués (avant tout traitement de ce projet). Le filtrage fonctionne malgré tout (clés normalisées), mais certains libellés texte restent partiellement reconstruits manuellement.
