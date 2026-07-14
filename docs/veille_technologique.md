## 1. RAG

Définition simple :

RAG (Retrieval Augmented Generation) est une technique qui permet à un LLM de rechercher des informations dans une base de connaissances avant de répondre.

Dans EDEN

Le RAG servira à :

rechercher les facteurs d'émission ADEME,
récupérer les valeurs CO2,
aider au calcul des émissions.
Exemple :
Consommation : 215 kWh
↓
Recherche ADEME
↓
Facteur : 0,0519 kgCO2e/kWh ("2024 - mix moyen", ADEME)
↓
Émission calculée
Ressource :
https://python.langchain.com/docs/concepts/rag/

## 2. LangChain

Définition simple :

LangChain est une bibliothèque Python qui permet de construire des applications basées sur les LLM.

Dans EDEN

Utilisé finalement pour une partie plus restreinte que prévu : charger les
PDF réglementaires (`PyPDFLoader`) et découper les documents en chunks
(`RecursiveCharacterTextSplitter`). L'appel à GPT-4o se fait directement via
le client `openai`, et la connexion à Chroma directement via `chromadb`
(`CloudClient`) — pas via les intégrations LangChain correspondantes.
Ressource :
https://python.langchain.com/

## 3. LangGraph

Définition simple :

LangGraph est une extension de LangChain qui permet de créer des agents IA sous forme de graphe.
| LangChain          | LangGraph                  |
| ------------------ | -------------------------- |
| Fournit les outils | Organise le déroulement    |
| Appelle un LLM     | Enchaîne plusieurs étapes  |
| Charge un PDF      | Décide quel chemin suivre  |
| Fait un RAG        | Gère la logique de l'agent |


## 4. Embeddings

Les embeddings transforment un texte en vecteur numérique.  
Cela permet de comparer des textes selon leur sens, et non seulement selon les mots exacts.

Dans EDEN, les embeddings permettront de transformer les facteurs d’émission ADEME en vecteurs afin de retrouver automatiquement le facteur le plus pertinent pour une donnée extraite d’une facture.

**Ressource :**  
- LangChain — Embedding models : https://docs.langchain.com/oss/python/integrations/embeddings

---

## 5. Chroma

Chroma est une base vectorielle open source utilisée pour stocker et rechercher des embeddings.

Dans EDEN, Chroma peut être utilisée pour stocker les documents ou facteurs d’émission ADEME et effectuer des recherches sémantiques.

**Ressource :**  
- LangChain — Chroma integration : https://docs.langchain.com/oss/python/integrations/vectorstores/chroma

---

## 6. FAISS

FAISS est une bibliothèque développée par Meta pour faire de la recherche rapide dans des vecteurs.

Dans EDEN, FAISS avait été envisagé comme alternative à Chroma, mais n'a
finalement pas été retenu ni utilisé : Chroma Cloud est la seule base
vectorielle du projet (voir `docs/architecture.md`).

**Ressource :**  
- FAISS documentation : https://faiss.ai/index.html

Dans EDEN

L'agent pourra suivre :

Facture
↓
OCR
↓
Extraction
↓
Recherche facteur ADEME
↓
Calcul CO2
↓
Rapport
Ressource :
https://langchain-ai.github.io/langgraph/