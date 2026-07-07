# Spécifications MVP — EDEN

## 1. Objectif du MVP

Le MVP couvre un chemin complet et fonctionnel : à partir d'une facture d'énergie au format PDF, extraire automatiquement les données de consommation, retrouver le facteur d'émission ADEME correspondant, et calculer les émissions de CO2e associées avec une source traçable. L'objectif n'est pas de couvrir tous les cas d'usage du produit final (Excel, données logistiques, relevés multi-sources, rapport CSRD complet), mais de valider que la chaîne OCR → extraction structurée → calcul carbone fonctionne de bout en bout sur des factures réelles, avec une fiabilité mesurée plutôt que supposée.

## 2. Pipeline actuel

1. **Facture PDF** reçue via l'endpoint `POST /extract/` (`backend/app/api/extract.py`).
2. **GPT-4o Vision** (`backend/app/ocr/gpt4o.py`) : le PDF est converti en images PNG (`pdf2image`, DPI 300), envoyées avec un prompt structuré au modèle `gpt-4o` (`temperature=0`). Le prompt demande directement un JSON structuré et contient des instructions explicites pour éviter les erreurs les plus fréquentes constatées en test (voir §5).
3. **JSON structuré** renvoyé par le modèle, au format harmonisé :
   `electricity_kwh, gas_m3, waste_tons, logistics_km, invoice_number, invoice_date, billing_period, supplier, amount_total, a_verifier, raison_verification`.
4. **`carbon.py`** (`backend/app/services/carbon.py`) calcule les émissions pour chaque champ de consommation présent :
   - lookup direct dans `facteurs_clean.json` quand un facteur cœur correspond (unité compatible) ;
   - sinon, recherche sémantique dans la collection Chroma `facteurs_emission`, avec filtre de compatibilité d'unité (rejette par exemple un facteur en `kgCO2e/t.km` pour une donnée en km seul).
5. **Résultat** : émissions en kgCO2e par champ + total, avec pour chaque valeur la source exacte utilisée (origine JSON direct ou RAG, nom du facteur, catégorie ADEME, identifiant ADEME si applicable).
6. La facture est aussi indexée dans Chroma (`energy-invoices`) et transmise à `agents/graph.py::run_eden`, qui enchaîne récupération de contexte réglementaire (RAG), calcul carbone, et génération d'un rapport (`report.py` — non testé bout en bout dans cette session, voir §4).

`tesseract.py` + `parser.py` (OCR classique + regex) restent dans le code mais ne sont plus utilisés par défaut (voir §5).

## 3. Périmètre couvert

- **Électricité** : `electricity_france`, mix moyen France continentale 2024, 0,0519 kgCO2e/kWh.
- **Gaz naturel** : `gas_naturel`, mix moyen, 2,32 kgCO2e/m3.
- **Transport routier**, 2 catégories : `transport_routier_poids_lourd` (rigide 12-20t diesel, 0,169 kgCO2e/t.km) et `transport_routier_utilitaire_leger` (VUL diesel, 0,842 kgCO2e/t.km).
- **Déchets d'activité économique non dangereux** : `dechets_dae` (DIB, ligne "Impacts" hors émissions évitées, 87,0 kgCO2e/tonne).

Ces 5 facteurs cœur sont dans `backend/knowledge/ademe/facteurs_clean.json`, dérivés de `base_carbone.csv` (script `clean_ademe.py`). En complément, la collection Chroma `facteurs_emission` contient les **12 014 lignes valides** (statut "Valide générique/spécifique") de la Base Carbone complète, tous secteurs confondus (alimentation, transport, déchets, bâtiment, numérique...), utilisée en repli sémantique quand aucun des 5 facteurs cœur ne correspond.

Une seconde collection Chroma, `reglementation`, indexe GHG Protocol, CSRD FAQ et ESRS E1 (929 chunks) pour la recherche de contexte réglementaire — utilisée par `retrieve_context()` mais pas encore reliée à un calcul ou une vérification de conformité concrète.

## 4. Ce qui n'est PAS couvert

- **Formats d'entrée** : seul le PDF de facture est géré. Les fichiers Excel, données logistiques et relevés d'énergie mentionnés dans `docs/architecture.md` comme sources cibles ne sont pas implémentés.
- **Rapport CSRD final** : `report.py` (génération via GPT-4o) existe et est appelé par `run_eden`, mais n'a pas été testé bout en bout dans cette session — sa qualité et sa fiabilité ne sont pas vérifiées.
- **Dashboard** : aucune interface de suivi ou de visualisation n'existe.
- **Orchestration réelle** : `agents/graph.py` est un enchaînement séquentiel de 3 appels de fonctions (contexte → calcul → rapport), pas un graphe LangGraph avec état, branchements ou reprise sur erreur, malgré le nom du module.
- **Transport/déchets au-delà des 2+1 catégories retenues** : les 49 catégories transport et 31 catégories déchets identifiées dans la Base Carbone n'ont pas toutes été triées ; seules celles jugées pertinentes ont été ajoutées aux facteurs cœur (voir §3).
- **Validation humaine du flag `a_verifier`** : le champ existe et est renseigné par le modèle, mais rien dans le pipeline ne l'exploite encore (pas de file d'attente de vérification, pas d'alerte).

## 5. Choix techniques justifiés

**GPT-4o Vision plutôt que Tesseract+regex, par défaut.** Testé sur 4 factures réelles (1 Iberdrola, 3 TotalEnergies) sur 3 champs critiques (consommation, date de facture, montant total) : GPT-4o Vision obtient 11/11 corrects après itérations (prompt + DPI), contre 7/11 pour Tesseract+regex. Le regex se trompait de façon récurrente mais différente selon le fournisseur : ligne de calcul de taxe confondue avec la consommation totale, date de mention légale confondue avec la date de facture, valeur tarifaire partielle confondue avec le total, montant en prose non reconnu. Chaque correction de regex réglait un cas sans garantir les suivants. GPT-4o Vision, avec un prompt explicite sur ces pièges récurrents, généralise mieux d'un fournisseur à l'autre sans code spécifique par format de facture. Le coût reste faible (≈0,01 $/facture), ce qui rend le choix défendable à l'échelle de centaines de factures. Tesseract+regex est conservé dans le code (non supprimé) comme solution de repli gratuite et locale, mais n'est plus le chemin par défaut.

**Lookup JSON direct + repli RAG, plutôt que RAG seul.** Pour les 4 types de consommation les plus fréquents (électricité, gaz, transport routier, déchets DAE), le facteur exact est fixé dans `facteurs_clean.json` : la valeur utilisée est toujours la même, choisie et vérifiée une fois, traçable par une clé stable. Une recherche sémantique seule sur 12 014 lignes pourrait renvoyer un facteur différent d'un appel à l'autre, ou dimensionnellement incompatible (ex : confondre un facteur en kgCO2e/t.km avec une donnée en km — ce cas s'est produit en test et a été corrigé par un filtre de compatibilité d'unité). Le RAG reste utile en repli pour les cas hors des 5 facteurs cœur, où la couverture prime sur la stabilité exacte de la valeur.

## 6. Limites connues

- **`a_verifier` / `raison_verification`** : ce flag signale les cas où seule une valeur de consommation qualifiée de référence/prévisionnelle/estimée a été trouvée (ex : facture de mensualisation sans consommation réelle facturée). Il est renseigné par le modèle mais rien ne l'exploite encore en aval.
- **Dépendance à la qualité d'image (DPI)** : à DPI 200 (défaut de `pdf2image`), l'extraction s'est montrée instable d'un appel à l'autre sur une facture (valeurs différentes à chaque appel malgré `temperature=0`). Passé à DPI 300, la même facture donne des résultats stables sur 3 sessions séparées. Le comportement à des DPI plus bas ou sur des scans de moins bonne qualité n'a pas été testé.
- **Non-déterminisme résiduel** : `temperature=0` réduit mais ne garantit pas une sortie identique à chaque appel (comportement documenté du modèle, pas un bug du code). Aucun mécanisme de vote/re-vérification n'est en place.
- **Parser regex historique (`parser.py`, non utilisé par défaut)** : conservé dans le code mais fragile dès que la mise en page change — plusieurs bugs identifiés en test (confusion taxe/consommation, date de mention légale, montant en prose non reconnu) ne sont corrigés que partiellement, pour un seul fournisseur.
- **Corruption d'encodage du CSV source** : `base_carbone.csv` contient une corruption irréversible des caractères accentués (avant tout traitement de ce projet). Le filtrage fonctionne malgré tout (clés normalisées), mais les libellés texte de certaines catégories dans `facteurs_emission` restent partiellement reconstruits manuellement, pas garantis fidèles à 100 % à l'original.
- **Aucun test automatisé** : la validation du pipeline repose sur des tests manuels ponctuels (script `ingest_rag.py`, scripts de test ad hoc), pas sur une suite de tests reproductible.
