# 🧾 Processus de création d’un nouveau devis client

## Objectif

Créer un devis client complet et cohérent à partir de :

- `info-compagnie.md` → informations globales de l’entreprise et paramètres par défaut
- `template-devis.md` → structure standard du devis
- informations spécifiques fournies par l’utilisateur (client + chantier + prestations + prix)

---

## 1) Fichiers d’entrée

### 1.1 Configuration entreprise (`info-compagnie.md`)

Ce fichier contient :

- les coordonnées entreprise
- la configuration TVA
- les paramètres financiers (acompte, délai de paiement, devise)
- les prix unitaires métier
- les mentions légales et conditions standards
- les options techniques par défaut (type peinture, couches, finition)

### 1.2 Template devis (`template-devis.md`)

Ce fichier définit :

- le format final du document
- les sections obligatoires
- les champs à remplacer

### 1.3 Données spécifiques du devis (fournies par l’utilisateur)

Données attendues :

- informations client
- lieu d’intervention
- description des travaux
- surfaces (m²) par zone
- prestations supplémentaires
- dates (émission, début, durée)
- mode de paiement (si différent du standard)

---

## 2) Données à demander à l’utilisateur

Si une donnée manque, la demander explicitement avant génération finale.

### 2.1 Informations client

- Nom
- Adresse
- Téléphone
- Email

### 2.2 Informations chantier

- Adresse du chantier
- Description détaillée des travaux
- Travaux complémentaires (optionnel)

### 2.3 Données techniques

- Type de peinture (sinon valeur par défaut)
- Nombre de couches (sinon valeur par défaut)
- Finition (sinon valeur par défaut)
- Surfaces :
  - Murs (m²)
  - Plafonds (m²)
  - Portes/Fenêtres (m² ou unité convertie)
  - Autres (m²)

### 2.4 Données de chiffrage

- Heures de main d’œuvre (ou calcul via surfaces)
- Fournitures (quantité/prix)
- Travaux préparatoires
- Prestations supplémentaires
- Frais de déplacement (si applicables)

### 2.5 Délais

- Date du devis
- Date de début estimée
- Durée estimée (jours ouvrables)

---

## 3) Règles de remplissage

### 3.1 Champs entreprise

Toujours injecter depuis `info-compagnie.md` :

- nom, adresse, téléphone, email, IDE, TVA
- IBAN et banque
- for juridique
- conditions standards

### 3.2 Numéro de devis

Construire selon :

- `prefixe_devis`
- `format_numero`
- année en cours
- compteur (incrémental)

Exemple :
`DEVIS-2026-0012`

### 3.3 Validité du devis

Calcul :

- `date_devis + validite_jours`

### 3.4 TVA

- Si `assujetti_tva = oui` :
  - afficher TVA avec `taux_tva`
  - Total TTC = HT + TVA
- Si `assujetti_tva = non` :
  - TVA = 0
  - afficher la mention légale :
    `Non assujetti à la TVA selon l’art. 10 LTVA`

### 3.5 Valeurs par défaut métier

Utiliser depuis `info-compagnie.md` si non précisées :

- `type_peinture`
- `nombre_couches`
- `finition`

---

## 4) Calculs financiers

## 4.1 Lignes de prix (exemple de logique)

- Main d’œuvre = `heures * prix_heure_main_oeuvre`
- Murs = `surface_murs * prix_m2_standard`
- Plafonds = `surface_plafonds * prix_m2_plafond`
- Déplacement = `prix_deplacement` (si facturé)
- - autres postes (fournitures, préparatoires, suppléments)

### 4.2 Totaux

- Sous-total HT = somme des lignes
- TVA = `Sous-total * taux_tva / 100` (si assujetti)
- Total TTC = `Sous-total + TVA`

### 4.3 Acompte et paiement

- Acompte = `% acompte_pourcentage` du TTC (ou HT selon politique)
- Solde payable à `delai_paiement_jours` jours

---

## 5) Génération du document final

1. Copier la structure de `template-devis.md`
2. Remplacer tous les placeholders `[ ... ]` par les valeurs calculées/fournies
3. Vérifier qu’aucun champ obligatoire ne reste vide
4. Ajouter les conditions générales et la mention TVA correcte
5. Sauvegarder sous un nom explicite, par exemple :
   - `devis-DEVIS-2026-0012-dupont.md`

---

## 6) Checklist de validation avant envoi

- [ ] Coordonnées entreprise correctes
- [ ] Coordonnées client complètes
- [ ] Numéro de devis unique
- [ ] Dates cohérentes (émission, validité, début)
- [ ] Surfaces et prestations complètes
- [ ] Totaux HT/TVA/TTC exacts
- [ ] Mention TVA conforme (assujetti ou non)
- [ ] Conditions de paiement présentes
- [ ] For juridique présent
- [ ] Signatures (zones client + entreprise) présentes

---

## 7) Format de sortie attendu

Le résultat final doit être :

- un fichier Markdown complet, prêt à envoyer
- lisible tel quel ou exportable en PDF
- conforme à la structure de `template-devis.md`

---
