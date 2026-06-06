# 📰 The Deal Brief

Newsletter hebdomadaire **M&A · Finance · IA · Géopolitique** — envoyée automatiquement chaque vendredi matin.

Conçue pour préparer des entretiens en banque d'affaires : chaque numéro explique les mécanismes en profondeur, pas juste l'actu de surface.

## Structure de chaque numéro

| Section | Contenu |
|---|---|
| 🔴 M&A & Marchés | 2 deals majeurs avec rationnel, structure, valorisation |
| 🟠 PE & VC | Actualité Private Equity + levée VC analysée |
| 🟡 Macro & Géopo | Donnée macro + tension géopolitique → impact marché |
| 🔵 IA | Deal ou mouvement stratégique IA |
| 📚 Rappel de cours | 4-5 notions techniques expliquées simplement |
| 🎯 Question d'entretien | 1 question + structure de réponse |

## Setup (5 min)

### 1. Cloner le repo
```bash
git clone https://github.com/<ton-username>/newsletter-mna.git
cd newsletter-mna
```

### 2. Configurer les secrets GitHub
Dans **Settings → Secrets and variables → Actions**, ajouter :

| Secret | Valeur |
|---|---|
| `ANTHROPIC_API_KEY` | Ta clé API Anthropic (https://console.anthropic.com) |
| `GMAIL_ADDRESS` | Ton adresse Gmail expéditrice |
| `GMAIL_APP_PASSWORD` | Mot de passe d'application Gmail (voir ci-dessous) |

**Créer un mot de passe d'application Gmail :**
1. Aller sur https://myaccount.google.com/security
2. Activer la validation en 2 étapes
3. Chercher "Mots de passe des applications"
4. Créer un mot de passe pour "Autre (nom personnalisé)" → `newsletter`
5. Copier le code à 16 caractères généré

### 3. Activer GitHub Actions
Les Actions se déclenchent automatiquement **chaque vendredi à 7h00 (Paris)**.

Pour un envoi manuel : **Actions → Newsletter hebdomadaire → Run workflow**

## Lancer en local

```bash
pip install -r requirements.txt

# Windows PowerShell
$env:ANTHROPIC_API_KEY="sk-ant-..."
$env:GMAIL_ADDRESS="ton@gmail.com"
$env:GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"

python generate_newsletter.py
```

## Améliorer la newsletter

- **Mise en page** : modifier `template.html`
- **Profondeur du contenu** : modifier `CONTENT_PROMPT` dans `generate_newsletter.py`
- **Fréquence** : modifier le `cron` dans `.github/workflows/newsletter.yml`
- **Archives** : chaque numéro est sauvegardé dans `archives/`
