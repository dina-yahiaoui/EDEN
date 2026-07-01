# Comparaison des solutions OCR pour EDEN

## Objectif

L’objectif de ce benchmark est de comparer trois solutions OCR pour extraire des données structurées à partir de factures d’énergie :

* Tesseract OCR
* GPT-4o Vision
* Mistral OCR

Le jeu de test contient 17 factures PDF. Les champs extraits sont normalisés au format JSON :

```json
{
  "electricity_kwh": null,
  "gas_m3": null,
  "waste_tons": null,
  "logistics_km": null,
  "invoice_number": "",
  "invoice_date": "",
  "billing_period": "",
  "supplier": "",
  "amount_total": null
}
```

## Comparaison technique

| Critère                | Tesseract OCR                 | GPT-4o Vision                                         | Mistral OCR                          |
| ---------------------- | ----------------------------- | ----------------------------------------------------- | ------------------------------------ |
| Type                   | OCR classique local           | Modèle multimodal                                     | OCR documentaire spécialisé          |
| Lecture PDF directe    | Non, nécessite `pdf2image`    | Non dans notre implémentation, conversion PDF → image | Oui, via upload PDF                  |
| Sortie brute           | Texte brut                    | JSON directement                                      | Markdown structuré                   |
| Qualité sur factures   | Moyenne                       | Très bonne                                            | Très bonne                           |
| Gestion des tableaux   | Faible à moyenne              | Bonne                                                 | Très bonne                           |
| Facilité d’intégration | Moyenne                       | Facile                                                | Moyenne                              |
| Coût                   | Gratuit                       | Payant à l’usage                                      | Payant / crédits API                 |
| Rapidité               | Correcte                      | Bonne                                                 | Bonne                                |
| Dépendances            | Tesseract + Poppler           | API OpenAI                                            | API Mistral                          |
| Pertinence pour EDEN   | Utile comme baseline gratuite | Très pertinent                                        | Très pertinent pour OCR documentaire |

## Résultats observés

### Tesseract OCR

Tesseract est une solution gratuite et locale. Elle permet d’extraire du texte brut à partir des factures après conversion du PDF en images avec `pdf2image`.

Cependant, la qualité dépend fortement de la mise en page, de la résolution du PDF et de la langue installée. Pour les factures françaises, il a fallu ajouter le fichier `fra.traineddata`.

Avantages :

* Gratuit
* Fonctionne localement
* Pas de coût API
* Utile comme solution de comparaison

Limites :

* Ne lit pas directement les PDF
* Moins robuste sur les tableaux
* Sortie non structurée
* Nécessite ensuite un LLM pour transformer le texte en JSON

### GPT-4o Vision

GPT-4o Vision a été utilisé pour analyser directement les images des pages des factures. Les PDF sont convertis en images avec `pdf2image`, puis chaque page est envoyée au modèle.

Cette solution a donné de bons résultats, notamment lorsque toutes les pages du PDF sont envoyées au modèle. Lors d’un premier test sur une seule page, certains champs comme la consommation en kWh n’étaient pas extraits. En envoyant toutes les pages, l’extraction est devenue plus complète.

Avantages :

* Très bonne compréhension visuelle des factures
* Extraction directe en JSON
* Bonne gestion des documents multipages
* Bon choix pour un prototype rapide

Limites :

* Dépend d’une API payante
* Nécessite une conversion PDF → image
* Coût à surveiller si le volume augmente

### Mistral OCR

Mistral OCR est une solution spécialisée dans l’OCR documentaire. Elle accepte directement les PDF après upload et retourne un Markdown structuré.

Les résultats sont très propres, notamment pour les titres, tableaux et sections de facture. Cependant, une étape supplémentaire est nécessaire pour transformer le Markdown en JSON normalisé.

Avantages :

* Lit les PDF directement
* Produit un Markdown structuré
* Bonne conservation de la structure du document
* Très adapté aux factures et documents longs

Limites :

* Nécessite une API Mistral
* Ne retourne pas directement le JSON métier attendu
* Nécessite une seconde étape avec un LLM pour structurer les données

## Choix retenu pour EDEN

Pour la suite du projet EDEN, la solution retenue est :

## GPT-4o Vision

Ce choix est motivé par plusieurs raisons :

1. Le modèle extrait directement les données au format JSON.
2. Il comprend bien les factures multipages.
3. Il permet de passer rapidement du document PDF aux champs métier utiles.
4. Il est simple à intégrer dans un pipeline Python.
5. Le coût observé pendant le benchmark reste faible pour un prototype.

Mistral OCR reste une très bonne alternative, notamment pour une future version plus robuste orientée documents complexes. Tesseract est conservé comme baseline gratuite et locale, mais il est moins adapté comme solution principale pour EDEN.

## Conclusion

Le benchmark montre que GPT-4o Vision est le meilleur choix pour le MVP EDEN, car il combine OCR visuel et extraction structurée en une seule étape.

Mistral OCR est également performant, surtout pour produire une représentation Markdown fiable du document. Tesseract est utile pour comparaison, mais moins fiable sur des factures complexes.

Pour le MVP, EDEN utilisera donc prioritairement GPT-4o Vision pour l’extraction des données depuis les factures.
