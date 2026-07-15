# Démo EDEN — guide de lancement

## 1. Ordre de lancement (depuis zéro)

**Ordre important** : Docker Desktop → n8n → FastAPI → Streamlit.

### 1. Docker Desktop
Lance l'application Docker Desktop et attends qu'elle soit complètement démarrée
(icône stable dans la barre des tâches) **avant** l'étape suivante — la commande
`docker run` échoue sinon.

### 2. n8n
```bash
docker run -it --rm --name n8n -p 5678:5678 -v n8n_data:/home/node/.n8n docker.n8n.io/n8nio/n8n
```
Laisse ce terminal ouvert. Si le webhook ne répond pas pendant la démo, vérifie
dans l'éditeur n8n (http://localhost:5678) que le workflow "rapport-csrd" est
bien **actif** (toggle en haut à droite de l'écran du workflow).

### 3. API FastAPI (nouveau terminal)
```bash
cd backend
uvicorn app.main:app --reload
```

### 4. Dashboard Streamlit (nouveau terminal)

Avant de lancer, vérifier qu'aucun ancien process Streamlit ne traîne déjà sur
le port 8501 (arrivé après un test précédent mal fermé) :
```bash
netstat -ano | findstr :8501
```
S'il y a une ligne en résultat, note le PID (dernière colonne) et tue le
process avant de continuer :
```bash
taskkill /PID <le_pid> /F
```
Puis lance le dashboard :
```bash
cd frontend
streamlit run app.py
```

## 2. URLs à ouvrir

| Service | URL | Usage |
|---|---|---|
| API FastAPI | http://localhost:8000/docs | Documentation interactive de l'API (test manuel des endpoints) |
| API FastAPI | http://localhost:8000/health | Vérification rapide que l'API tourne |
| Dashboard Streamlit | http://localhost:8501 | Interface principale de la démo |
| n8n | http://localhost:5678 | Éditeur du workflow, pour vérifier qu'il est actif ou voir l'historique d'exécutions |

## 3. Factures de test recommandées pour la démo

Toutes dans `data/raw/`.

| Facture | Ce qu'elle montre |
|---|---|
| `facture_01.pdf` | Cas normal : extraction électricité, calcul CO2eq (scope 2), rapport et webhook OK |
| `facture_04.pdf` | Cas `a_verifier` / `erreur_extraction` : facture de mensualisation sans consommation réelle — montre la gestion d'échec propre (pas de crash, statut clair) |
| `facture_18_gaz_test.pdf` | Scope 1 (gaz), facteur trouvé en JSON direct (2,32 kgCO2e/m³) |
| `facture_19_transport_test.pdf` | Scope 3 (transport), facteur trouvé via **RAG sémantique** (pas de facteur JSON direct pour le km seul) |
| `facture_20_dechets_test.pdf` | Scope 3 (déchets), facteur trouvé en **JSON direct** (87 kgCO2e/tonne) |

Pour montrer les 3 scopes GHG Protocol en une démo courte : `facture_01` (scope 2) →
`facture_18` (scope 1) → `facture_19` ou `facture_20` (scope 3). Pour montrer la
gestion d'erreur : enchaîner avec `facture_04`.

D'autres factures existent dans `data/raw/` (02, 03, 05 à 17) si besoin de plus
de variété, mais celles listées ci-dessus couvrent chaque cas de figure
important sans redondance.


