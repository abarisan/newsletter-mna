"""
Newsletter M&A · Finance · IA · Géopolitique
Génère le contenu via Claude API + envoie par email chaque vendredi.
"""

import google.generativeai as genai
import smtplib
import os
import re
import json
import datetime
import genanki
import random
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

# Rythme quotidien lun-ven
DAY_FORMAT = {
    0: "LUNDI",
    1: "MARDI",
    2: "MERCREDI",
    3: "JEUDI",
    4: "VENDREDI",
}


RECIPIENT_EMAIL = "sooriyakumar.abarisan@gmail.com"
SENDER_EMAIL    = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASS  = os.environ["GMAIL_APP_PASSWORD"]
GEMINI_KEY      = os.environ["GEMINI_API_KEY"]


import feedparser

# ─────────────────────────────────────────────────────────────────────────────
# GEMINI CLIENT
# ─────────────────────────────────────────────────────────────────────────────

def gemini_call(prompt: str, system: str = "", max_tokens: int = 8000) -> str:
    """Appelle Gemini 2.0 Flash et retourne le texte de la réponse."""
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=system if system else None,
        generation_config=genai.GenerationConfig(max_output_tokens=max_tokens)
    )
    response = model.generate_content(prompt)
    return response.text


# ─────────────────────────────────────────────────────────────────────────────
# SCRAPING RSS — actus M&A en temps réel
# ─────────────────────────────────────────────────────────────────────────────

RSS_FEEDS = [
    ("CNBC Finance",    "N1", "https://www.cnbc.com/id/10000049/device/rss/rss.html"),
    ("FT",              "N1", "https://www.ft.com/rss/home"),
    ("WSJ Markets",     "N3", "https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines"),
    ("MarketWatch",     "N1", "https://feeds.marketwatch.com/marketwatch/marketpulse/"),
    ("NYT DealBook",    "N2", "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml"),
]

def fetch_recent_news(max_per_feed: int = 5) -> str:
    """Récupère les dernières actus M&A/finance via RSS et retourne un résumé texte."""
    items = []
    for name, level, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_per_feed]:
                title   = entry.get("title", "").strip()
                summary = entry.get("summary", entry.get("description", "")).strip()
                # Nettoie le HTML basique dans le summary
                import re
                summary = re.sub(r"<[^>]+>", " ", summary)[:200].strip()
                published = entry.get("published", "")[:16]
                if title:
                    items.append(f"[{level} · {name}] {title} ({published})\n  → {summary}")
        except Exception:
            pass  # On ignore les feeds qui tombent

    if not items:
        return "Aucune actu récupérée via RSS (feeds indisponibles)."

    return "## Actus M&A récentes — flux RSS en temps réel\n\n" + "\n\n".join(items[:25])


SYSTEM_PROMPT = """Tu es un analyste M&A senior qui rédige une newsletter hebdomadaire pour un étudiant
préparant des entretiens en banque d'affaires (M&A).

## Ta philosophie éditoriale

**La news illustre le cours, jamais l'inverse.**
Tu ne choisis pas une actu pour remplir la newsletter. Tu choisis l'actu qui permet d'enseigner
un concept précis cette semaine. Si le deal EA permet d'expliquer la mécanique LBO, c'est lui
qu'on prend. Si une décision de la Fed permet d'expliquer le WACC, c'est ça le fil directeur.
Le cours et la news sont la même chose — l'un explique l'autre.

**Progression technique stricte.**
Chaque numéro part du principe que le lecteur a lu les précédents. On ne réexplique pas ce
qui a déjà été couvert. On va plus loin, on affine, on complexifie. La progression doit
ressembler à celle d'un cours : semaine 1 = mécanique LBO, semaine 2 = modélisation LBO,
semaine 3 = structure de la dette dans un LBO, semaine 4 = covenants et credit agreement.

**Suivi des deals dans le temps.**
Un deal annoncé reste vivant jusqu'à sa clôture. Tu reviens dessus quand il y a du nouveau :
approbation réglementaire, émission obligataire, révision de prix, réaction du marché. Chaque
retour sur un deal est l'occasion d'approfondir un point technique différent.

**Sources obligatoires — au moins une par niveau chaque semaine :**

| Niveau | Publications | Usage |
|--------|-------------|-------|
| 1 — Indispensables | Capital Finance, Bloomberg, CFNEWS, Financial Times, S&P Global | Deals, marchés, tendances sectorielles |
| 2 — Pour aller plus loin | Mergermarket, Reuters, PitchBook | Détails transactions, PE, VC, mouvements stratégiques |
| 3 — Pour briller | Wall Street Journal, The Economist | Macro, géopolitique, grands cycles |
| 4 — Niche & data | Dealogic, Preqin | Données PE/M&A, fundraising, statistiques |

Tu dois citer explicitement au moins une source de chaque niveau dans le numéro.
Pour le deal principal, cite au minimum une source N1 + une source N2.
Pour la macro/géopo, cite au minimum une source N3.
Pour les données chiffrées sur le marché, cite au minimum une source N4 si disponible.

**Règles absolues :**
- Langue : français, ton direct et pédagogique, jamais condescendant
- Chiffres précis, sources nommées avec titre d'article si possible
- Jamais de généralités : toujours un acteur nommé, un chiffre, une date
"""

CONTENT_PROMPT_DAILY = """Génère le contenu de THE DEAL BRIEF N°{numero} — {date} ({jour}).

## Contexte des numéros précédents
{previous_issues}

---

## Construction du numéro

**Étape 1 : le chapitre du jour est fixé** (voir section "Programme de cours" dans le contexte).
Choisis le deal réel le plus récent qui illustre CE chapitre précisément.
Si un deal déjà ouvert a du nouveau ET colle au chapitre, reviens dessus.

**Étape 2 : cours en profondeur.**
Le chapitre TRAINY est le fil directeur. Va aussi loin que possible techniquement.
Lien explicite avec le deal : "dans ce deal, on voit que X — voilà pourquoi".
Progression : mécanique de base → complexification → chiffres réels → cas limite ou erreur classique en entretien.
Annonce ce qu'on verra demain (prochain chapitre).

**Étape 3 : signal macro.**
Y a-t-il un fait macro/géopo cette semaine qui éclaire directement le deal ou le concept du jour ?
Si oui, 1 paragraphe de lien explicite. Sinon, le signal macro le plus impactant pour le M&A.

---

## Structure complète

### 1. DEAL — [titre accrocheur]
- Ce qui s'est passé (deal nouveau ou avancée sur un deal ouvert)
- Chiffres précis : prix, prime, levier, structure equity/dette, banques conseil
- Rationnel stratégique : pourquoi maintenant, pourquoi ces acteurs
- Zoom technique : l'aspect du deal qui illustre directement le chapitre du jour
- Phrase d'entretien prête à l'emploi (2-3 lignes avec opinion personnelle)

### 2. SIGNAL MACRO & GÉOPOLITIQUE
- 1 fait précis avec date et source
- Mécanisme de transmission vers le M&A : coût de la dette, valorisations, appétit acheteurs

### 3. COURS — [titre = concept précis du chapitre TRAINY, jamais "rappel de cours"]
- Intro : lien avec le deal et les numéros précédents
- Corps complet et profond : progression simple → complexe, chiffres tirés du deal réel
- Encadrés de définitions pour les termes techniques clés
- Fin : ce que le lecteur sait maintenant + ce qu'on verra demain

### 4. QUESTION D'ENTRETIEN
- Directement inspirée du cours et du deal de CE numéro
- Réponse structurée en 2-3 points avec les bons termes techniques

---

RÈGLES ABSOLUES SUR LE JSON :
- `ma_contenu` : minimum 4 paragraphes <p> avec chiffres précis, rationnel, zoom technique, phrase d'entretien
- `rappel_cours` : OBLIGATOIRE et LONG — c'est le cœur du numéro. Minimum 600 mots. Mécanique complète du chapitre TRAINY du jour, avec définitions encadrées (<div class='term'>), exemples chiffrés, cas limites, erreurs classiques en entretien.
- `macro_titre` + `macro_contenu` : toujours remplis, jamais vides
- `question_entretien` : une vraie question précise entre guillemets, jamais vide
- `reponse_structuree` : réponse complète en 3 points minimum avec les bons termes techniques

Retourne UNIQUEMENT ce JSON :
{{
  "numero": "{numero}",
  "date": "{date}",
  "jour": "{jour}",
  "ma_titre": "...",
  "ma_contenu": "HTML avec <p> <strong> <em> <ul> <ol> et class='callout' — MINIMUM 4 paragraphes",
  "macro_titre": "...",
  "macro_contenu": "HTML — toujours rempli",
  "ia_titre": "...",
  "ia_contenu": "HTML ou chaîne vide si pas pertinent",
  "rappel_cours": "HTML LONG avec <p> <strong> <em> <ul> <ol> et <div class='term'><div class='term-name'>TERME</div>Définition...</div> — MINIMUM 600 mots",
  "question_entretien": "Question précise entre guillemets — jamais vide",
  "reponse_structuree": "HTML avec 3 points minimum — jamais vide",
  "sources": ["[N1] Bloomberg ou FT ou Capital Finance — titre", "[N2] Mergermarket ou Reuters — titre", "[N3] WSJ ou The Economist — titre", "[N4] Dealogic ou Preqin — donnée (si dispo)"]
}}
"""

CONTENT_PROMPT_LUNDI = """Génère le contenu du LUNDI pour THE DEAL BRIEF N°{numero} — {date}.

## Contexte des numéros précédents
{previous_issues}

## Objectif du lundi : poser le deal de la semaine

Le lundi sert à introduire UN deal réel et récent qui sera le fil conducteur de la semaine.
Le mercredi, on creusera le concept technique qu'il illustre. Le vendredi, on prendra du recul macro.

### Structure

**1. DEAL DE LA SEMAINE**
- Ce qui vient de se passer (ou une avancée sur un deal précédent encore ouvert)
- Chiffres précis : prix, prime, levier, structure, banques conseil
- Rationnel côté acquéreur et côté cible
- 1 point technique à retenir (sera approfondi mercredi)
- Phrase d'entretien prête à l'emploi

**2. POURQUOI CE DEAL CETTE SEMAINE**
- Ce qu'il dit sur l'état du marché M&A en ce moment
- Le concept clé qu'il illustre et qu'on creusera mercredi (annonce ce qui vient)

Retourne UNIQUEMENT ce JSON :
{{
  "numero": "{numero}",
  "date": "{date}",
  "jour": "Lundi",
  "ma_titre": "...",
  "ma_contenu": "HTML...",
  "macro_titre": "À creuser mercredi : [nom du concept]",
  "macro_contenu": "<p>Ce deal pose une question technique centrale : <strong>[concept]</strong>. Mercredi, on décortique exactement comment ça fonctionne à partir des chiffres de ce deal.</p>",
  "ia_titre": "",
  "ia_contenu": "",
  "rappel_cours": "",
  "question_entretien": "...",
  "reponse_structuree": "HTML...",
  "sources": ["[N1] Bloomberg — ...", "[N2] Mergermarket — ...", "[N3] WSJ ou The Economist — ...", "[N4] Dealogic ou Preqin — ... (si dispo)"]
}}
"""

CONTENT_PROMPT_MERCREDI = """Génère le contenu du MERCREDI pour THE DEAL BRIEF N°{numero} — {date}.

## Contexte des numéros précédents
{previous_issues}

## Objectif du mercredi : cours en profondeur ancré dans le deal du lundi

Tu reprends le deal introduit lundi et tu l'utilises comme terrain d'apprentissage pour
expliquer UN concept technique en profondeur. Le lecteur connaît déjà le deal — maintenant
il comprend POURQUOI les choses ont été structurées ainsi.

La progression technique doit être un cran au-dessus du dernier cours publié.

### Structure

**1. RAPPEL DU DEAL** (3 lignes max — le lecteur sait déjà)
- Juste assez pour contextualiser le cours

**2. COURS — [titre = concept précis, pas "rappel de cours"]**
- Début : "Dans le deal X, on a vu que Y. Pourquoi ?"
- Mécanique de base → complexification → chiffres réels tirés du deal → cas limite ou erreur classique
- Lien avec la progression des semaines précédentes (cite ce qu'on a déjà couvert)
- Fin : "La semaine prochaine / vendredi, on verra comment le signal macro de cette semaine
  change l'équation"

**3. QUESTION D'ENTRETIEN TECHNIQUE**
- Question précise sur le concept enseigné ce jour
- Réponse structurée avec les bons termes

Retourne UNIQUEMENT ce JSON :
{{
  "numero": "{numero}",
  "date": "{date}",
  "jour": "Mercredi",
  "ma_titre": "Retour sur [nom du deal] : [concept à expliquer]",
  "ma_contenu": "<p>Rappel rapide du deal...</p>",
  "macro_titre": "",
  "macro_contenu": "",
  "ia_titre": "",
  "ia_contenu": "",
  "rappel_cours": "HTML du cours complet et profond...",
  "question_entretien": "...",
  "reponse_structuree": "HTML...",
  "sources": ["[N1] Bloomberg — ...", "[N2] Mergermarket — ...", "[N3] WSJ ou The Economist — ...", "[N4] Dealogic ou Preqin — ... (si dispo)"]
}}
"""

CONTENT_PROMPT_VENDREDI = """Génère le contenu du VENDREDI pour THE DEAL BRIEF N°{numero} — {date}.

## Contexte des numéros précédents
{previous_issues}

## Objectif du vendredi : recul macro + question d'entretien de fin de semaine

Le vendredi, on prend de la hauteur. On connecte le signal macro de la semaine au deal
qu'on a suivi lundi et mercredi. L'objectif : montrer que la macro n'est pas abstraite,
elle change concrètement le prix des deals, le coût de la dette, l'appétit des acheteurs.

### Structure

**1. SIGNAL MACRO / GÉOPOLITIQUE**
- 1 fait précis de cette semaine (chiffre, décision de banque centrale, tension géopo)
- Mécanisme de transmission direct vers le M&A : comment ça change les deals concrètement ?
- Lien avec le deal de cette semaine si possible

**2. IA & FINANCE** (uniquement si un fait marquant cette semaine directement lié au M&A)

**3. QUESTION D'ENTRETIEN DE FIN DE SEMAINE**
- Question qui connecte le deal de lundi, le cours de mercredi et la macro de vendredi
- Ex : "Comment la hausse des taux de la Fed affecte-t-elle la capacité d'endettement
  dans un LBO comme celui d'EA ?"
- Réponse complète et structurée

Retourne UNIQUEMENT ce JSON :
{{
  "numero": "{numero}",
  "date": "{date}",
  "jour": "Vendredi",
  "ma_titre": "",
  "ma_contenu": "",
  "macro_titre": "...",
  "macro_contenu": "HTML...",
  "ia_titre": "...",
  "ia_contenu": "HTML ou vide",
  "rappel_cours": "",
  "question_entretien": "...",
  "reponse_structuree": "HTML...",
  "sources": ["[N1] Bloomberg — ...", "[N2] Mergermarket — ...", "[N3] WSJ ou The Economist — ...", "[N4] Dealogic ou Preqin — ... (si dispo)"]
}}
"""

CONTENT_PROMPT = """Génère le contenu complet pour THE DEAL BRIEF N°{numero} — {date}.

## Contexte des numéros précédents
{previous_issues}

---

## Construction du numéro — raisonne dans cet ordre

**Étape 1 : choisis le fil directeur.**
Quelle est l'actu M&A/finance la plus instructive de cette semaine ? Pas la plus grosse —
la plus utile pédagogiquement. C'est elle qui détermine TOUT le reste du numéro.

Si un deal précédent a du nouveau (avancée réglementaire, émission de dette, réaction des
marchés, révision de prix), reviens dessus plutôt que de chercher un nouveau deal. La continuité
est plus précieuse que la nouveauté.

**Étape 2 : identifie le concept à enseigner.**
Quelle notion technique cette actu permet-elle d'illustrer parfaitement ? C'est ton cours de
la semaine. Il doit être la suite logique du cours précédent — un cran plus technique, une
couche supplémentaire sur le même édifice. Si le N°1 a couvert la mécanique LBO, le N°2
modélise, le N°3 détaille la dette, le N°4 explique les covenants.

**Étape 3 : construis le signal macro.**
Y a-t-il un fait macro ou géopo cette semaine qui éclaire directement le deal choisi ?
(ex : si le deal est un LBO, une décision de la Fed sur les taux est directement pertinente)
Si oui, 1 paragraphe de lien explicite. Si non, choisis le signal macro le plus impactant
pour le M&A en général cette semaine.

---

## Structure du numéro

### 1. DEAL — [titre accrocheur]
- Ce qui s'est passé cette semaine sur ce deal (nouveau ou suivi d'un précédent)
- Chiffres précis : prix, prime, levier, structure equity/dette, banques conseil
- Rationnel stratégique : pourquoi maintenant, pourquoi ces acteurs
- Point technique zoom : 1 aspect précis du deal qui mérite d'être décortiqué
  (ex : pourquoi l'émission high yield plutôt que du prêt bancaire ? comment la prime
  de 25% a-t-elle été justifiée ? quel est le plan de sortie du fonds ?)
- Phrase d'entretien : 2-3 lignes prêtes à l'emploi, avec une opinion personnelle

### 2. SIGNAL MACRO
- 1 fait précis (chiffre, décision, événement) avec date et source
- Mécanisme de transmission vers le M&A : comment ça affecte le coût de la dette,
  les valorisations, l'appétit des acheteurs stratégiques ou financiers ?

### 3. COURS — [titre = concept précis, pas générique]
- Intro : lien explicite avec le deal et les numéros précédents ("on a vu X, on va maintenant
  comprendre Y qui est ce qui explique pourquoi dans le deal EA...")
- Corps : progression claire du simple vers le complexe, avec chiffres tirés du deal réel
- Fin : ce que le lecteur sait maintenant qu'il ne savait pas avant, et ce qu'on verra ensuite

### 4. QUESTION D'ENTRETIEN
- Directement inspirée du cours et du deal de CE numéro
- Structure de réponse en 2-3 points, avec les bons termes techniques

---

Retourne UNIQUEMENT le contenu JSON suivant :
{{
  "numero": "{numero}",
  "date": "{date}",
  "ma_titre": "...",
  "ma_contenu": "HTML avec balises <p> <strong> <em> <ol> <ul> <li> et class='callout'",
  "macro_titre": "...",
  "macro_contenu": "HTML...",
  "ia_titre": "...",
  "ia_contenu": "HTML ou chaîne vide si pas pertinent cette semaine",
  "rappel_cours": "HTML avec balises <p> <strong> <em> <ol> <ul> et <div class='term'><div class='term-name'>...</div>",
  "question_entretien": "La question entre guillemets",
  "reponse_structuree": "HTML...",
  "sources": ["[N1] Bloomberg — titre", "[N1] FT ou Capital Finance — titre", "[N2] Mergermarket ou Reuters — titre", "[N3] WSJ ou The Economist — titre", "[N4] Dealogic ou Preqin — donnée (si disponible)"]
}}
"""


def load_previous_issues(archive_dir: Path, max_issues: int = 3) -> str:
    """Résume les derniers numéros pour assurer la continuité éditoriale."""
    archives = sorted(archive_dir.glob("newsletter_*.html"), reverse=True)[:max_issues]
    if not archives:
        return "Aucun numéro précédent — c'est le N°1. Commence par les bases."

    summaries = []
    for path in archives:
        # Extrait le numéro et la date du nom de fichier (newsletter_2026-06-06.html)
        date_part = path.stem.replace("newsletter_", "")
        summaries.append(f"- {date_part} : {path.name} (disponible en archive)")

    return (
        "Numéros précédents publiés :\n" + "\n".join(summaries) + "\n\n"
        "Assure-toi que le cours de ce numéro va un cran plus loin que le précédent "
        "et que tu reviens sur les deals encore ouverts si du nouveau est disponible."
    )


def get_next_issue_number(archive_dir: Path) -> str:
    """Calcule le numéro du prochain numéro."""
    archives = list(archive_dir.glob("newsletter_*.html"))
    return str(len(archives) + 1).zfill(2)


def get_day_prompt(weekday: int) -> str:
    """Retourne le prompt du jour — quotidien par défaut."""
    return CONTENT_PROMPT_DAILY


def generate_content(date_str: str, archive_dir: Path, weekday: int, level: dict) -> dict:
    """Appelle Claude pour générer le contenu de la newsletter."""
    import json

    numero          = get_next_issue_number(archive_dir)
    previous_issues = load_previous_issues(archive_dir)
    prompt_template = get_day_prompt(weekday)

    # Actus RSS en temps réel
    print("📡 Récupération des actus RSS...")
    live_news = fetch_recent_news()

    # Chapitre TRAINY en cours
    idx     = level.get("trainy_index", 0)
    lesson  = get_lesson(idx)
    next_l  = get_next_lesson(idx)
    trainy_context = (
        f"\n## Programme de cours (TRAINY)\n"
        f"Chapitre en cours — Module {lesson['module']} · {lesson['titre_module']} : "
        f"**{lesson['titre']}** ({lesson['duree']})\n"
        f"Prochain chapitre : Module {next_l['module']} · {next_l['titre']} ({next_l['duree']})\n\n"
        f"Le cours du mercredi DOIT couvrir ce chapitre précisément. "
        f"Le deal du lundi et la question d'entretien doivent l'illustrer concrètement. "
        f"Ne couvre pas le prochain chapitre cette semaine.\n"
    )

    jour = DAY_FORMAT.get(weekday, "LUNDI")
    prompt = prompt_template.format(
        date=date_str,
        numero=numero,
        jour=jour,
        previous_issues=previous_issues + trainy_context + "\n\n" + live_news
    )

    def extract_json(text: str) -> dict:
        """Extrait et parse le premier JSON valide dans le texte."""
        text = re.sub(r"```json\s*", "", text)
        text = re.sub(r"```\s*", "", text)
        start = text.find("{")
        end   = text.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("Aucun JSON trouvé dans la réponse")
        return json.loads(text[start:end])

    text = gemini_call(prompt, system=SYSTEM_PROMPT, max_tokens=8000)
    try:
        content = extract_json(text)
    except (json.JSONDecodeError, ValueError) as e:
        raise RuntimeError(f"Gemini n'a pas retourné de JSON valide : {e}\n{text[:500]}")

    # Validation : les champs critiques ne doivent pas être vides
    required = ["ma_titre", "ma_contenu", "rappel_cours", "question_entretien", "reponse_structuree"]
    missing  = [k for k in required if not str(content.get(k, "")).strip()]
    if missing:
        print(f"  Champs vides : {missing} — retry...")
        retry_prompt = (
            prompt + f"\n\nATTENTION : ta réponse précédente avait ces champs vides : {missing}. "
            "Tu DOIS remplir TOUS les champs, notamment rappel_cours (cours complet du chapitre), "
            "question_entretien et reponse_structuree. Regenere un JSON complet."
        )
        try:
            content = extract_json(gemini_call(retry_prompt, system=SYSTEM_PROMPT, max_tokens=8000))
        except (json.JSONDecodeError, ValueError):
            pass  # On garde le premier résultat si le retry rate aussi

    return content


# ─────────────────────────────────────────────────────────────────────────────
# NIVEAU ADAPTATIF
# ─────────────────────────────────────────────────────────────────────────────

LEVEL_FILE = Path(__file__).parent / "level.json"

# ─── Plan de cours TRAINY ───────────────────────────────────────────────────
TRAINY_CURRICULUM = [
    # MODULE 1 — Accounting Fundamentals
    {"module": 1, "titre_module": "Accounting Fundamentals", "video": 1, "titre": "Financial Disclosure (US vs Europe)", "duree": "3 min"},
    {"module": 1, "titre_module": "Accounting Fundamentals", "video": 2, "titre": "Income Statement (P&L, EBITDA, EBIT, D&A, COGS, OPEX)", "duree": "40 min"},
    {"module": 1, "titre_module": "Accounting Fundamentals", "video": 3, "titre": "Cash Flow Statement (Operating / Investing / Financing)", "duree": "31 min"},
    {"module": 1, "titre_module": "Accounting Fundamentals", "video": 4, "titre": "Balance Sheet (Assets & Liabilities)", "duree": "46 min"},
    {"module": 1, "titre_module": "Accounting Fundamentals", "video": 5, "titre": "Links between the 3 financial statements", "duree": "25 min"},
    {"module": 1, "titre_module": "Accounting Fundamentals", "video": 6, "titre": "Working Capital (variations, BS vs CFS)", "duree": "19 min"},
    {"module": 1, "titre_module": "Accounting Fundamentals", "video": 7, "titre": "Goodwill", "duree": "10 min"},
    {"module": 1, "titre_module": "Accounting Fundamentals", "video": 8, "titre": "EPS & Diluted EPS", "duree": "10 min"},
    # MODULE 2 — Advanced Accounting
    {"module": 2, "titre_module": "Advanced Accounting", "video": 1, "titre": "Consolidation Methods & Group Accounts (full / proportionate / equity)", "duree": "31 min"},
    {"module": 2, "titre_module": "Advanced Accounting", "video": 2, "titre": "Calendarisation (LTM, NTM, YTD, FY, CY)", "duree": "10 min"},
    {"module": 2, "titre_module": "Advanced Accounting", "video": 3, "titre": "Financial Projections (drivers, business plan)", "duree": "8 min"},
    {"module": 2, "titre_module": "Advanced Accounting", "video": 4, "titre": "Focus on Inventories (LIFO, FIFO, WAC)", "duree": "8 min"},
    # MODULE 3 — The EV/Equity Bridge
    {"module": 3, "titre_module": "The EV/Equity Bridge", "video": 1, "titre": "What is the EV/EqV Bridge (net debt, step by step)", "duree": "32 min"},
    {"module": 3, "titre_module": "The EV/Equity Bridge", "video": 2, "titre": "Diluted Equity Value & Treasury Stock Method", "duree": "14 min"},
    {"module": 3, "titre_module": "The EV/Equity Bridge", "video": 3, "titre": "Dette vs Equity (coût, types, séniorité, faillite)", "duree": "33 min"},
    # MODULE 4 — Valuation Methods
    {"module": 4, "titre_module": "Valuation Methods", "video": 1, "titre": "Overview of all valuation methods (comparaison, cas d'usage)", "duree": "19 min"},
    {"module": 4, "titre_module": "Valuation Methods", "video": 2, "titre": "Trading Comparables (peers cotés, multiples)", "duree": "28 min"},
    {"module": 4, "titre_module": "Valuation Methods", "video": 3, "titre": "Precedent Transactions", "duree": "18 min"},
    {"module": 4, "titre_module": "Valuation Methods", "video": 4, "titre": "Walk me through a DCF", "duree": "31 min"},
    {"module": 4, "titre_module": "Valuation Methods", "video": 5, "titre": "Focus on WACC (calcul détaillé)", "duree": "24 min"},
    {"module": 4, "titre_module": "Valuation Methods", "video": 6, "titre": "The LBO Method (étapes complètes)", "duree": "25 min"},
    {"module": 4, "titre_module": "Valuation Methods", "video": 7, "titre": "Paper LBO (cas numérique, MoM & IRR)", "duree": "14 min"},
    # MODULE 5 — Focus on M&A Operations
    {"module": 5, "titre_module": "Focus on M&A Operations", "video": 1, "titre": "Mergers & Acquisitions Operations (synergies, accretive/dilutive)", "duree": "19 min"},
    {"module": 5, "titre_module": "Focus on M&A Operations", "video": 2, "titre": "Buy-Side & Sell-Side Processes", "duree": "9 min"},
    # MODULE 6 — Fit, Brainteasers & Calculus
    {"module": 6, "titre_module": "Fit, Brainteasers & Calculus", "video": 1, "titre": "Brainteasers & Market Sizing", "duree": "2 min"},
    {"module": 6, "titre_module": "Fit, Brainteasers & Calculus", "video": 2, "titre": "Fit Preparation (motivation, 'why you?', deal récent)", "duree": "11 min"},
]

def get_lesson(index: int) -> dict:
    """Retourne le chapitre TRAINY à l'index donné (modulo si on a tout fini)."""
    return TRAINY_CURRICULUM[index % len(TRAINY_CURRICULUM)]

def get_next_lesson(index: int) -> dict:
    return TRAINY_CURRICULUM[(index + 1) % len(TRAINY_CURRICULUM)]

DEFAULT_LEVEL = {
    "numero": 0,
    "depth": 1,             # 1=débutant → 10=expert
    "concepts_vus": [],     # concepts déjà couverts
    "deals_ouverts": [],    # deals à suivre
    "objectif": "Préparer des entretiens M&A dans 1 mois, puis sur 2-3 ans",
    "trainy_index": 0,      # position dans TRAINY_CURRICULUM (0-based)
}

def load_level() -> dict:
    if LEVEL_FILE.exists():
        return json.loads(LEVEL_FILE.read_text(encoding="utf-8"))
    return DEFAULT_LEVEL.copy()

def save_level(level: dict):
    LEVEL_FILE.write_text(json.dumps(level, ensure_ascii=False, indent=2), encoding="utf-8")


# ─────────────────────────────────────────────────────────────────────────────
# SCHÉMA SVG PÉDAGOGIQUE
# ─────────────────────────────────────────────────────────────────────────────

DIAGRAM_PROMPT = """Génère un schéma SVG simple et lisible pour illustrer ce point précis d'une newsletter M&A.

STYLE : minimaliste, aéré, 2-4 éléments maximum. Pas de surcharge. Des boîtes, des flèches, des chiffres clés.

Palette :
- Fond boîtes : #fff3e8 ou #ffffff
- Bordures / accents : #e85d1a
- Texte principal : #2b1a0e
- Texte secondaire : #7a5c45
- Flèches : #f9a06b
- Mise en avant : #c94e0e

Contraintes techniques strictes (email HTML) :
- SVG inline, AUCUNE ressource externe
- Largeur : 540px — hauteur : 160px à 220px MAX (schéma compact)
- Police Arial ou sans-serif uniquement, attributs inline
- PAS de <style>, PAS de foreignObject, PAS de clipPath
- Flèches : utilise <line> + <polygon> ou <marker> simple

Type de schéma selon le sujet :
- Deal / structure → 2-3 boîtes reliées par flèches avec chiffres clés
- Processus → timeline 3-4 étapes horizontale
- Concept financier → formule visuelle ou comparaison avant/après
- Macro → 2 cases cause → effet avec flèche

Sujet à illustrer : {sujet}
Données clés à inclure : {donnees}

Retourne UNIQUEMENT le SVG. Commence par <svg et termine par </svg>.
"""

def _extract_svg(text: str) -> str:
    start = text.find("<svg")
    end   = text.rfind("</svg>") + 6
    return text[start:end] if start != -1 and end > 6 else ""

def generate_diagrams(content: dict) -> dict:
    """Génère 2-3 schémas SVG simples pour le deal, le cours et la macro."""
    diagrams = {}

    # Sujets avec fallback pour éviter les champs vides
    deal_sujet  = content.get("ma_titre", "") or "Structure d'un deal M&A"
    deal_data   = content.get("ma_contenu", "")[:300] or content.get("macro_contenu", "")[:300]
    cours_sujet = content.get("rappel_cours", "")[:200] or content.get("ma_titre", "") or "Concept financier clé"
    cours_data  = content.get("rappel_cours", "")[:300] or content.get("ma_contenu", "")[:300]
    macro_sujet = content.get("macro_titre", "") or "Signal macro et impact M&A"
    macro_data  = content.get("macro_contenu", "")[:250] or content.get("ma_contenu", "")[:250]

    specs = [
        ("diagram_deal",  deal_sujet,  deal_data),
        ("diagram_cours", cours_sujet, cours_data),
        ("diagram_macro", macro_sujet, macro_data),
    ]

    for key, sujet, donnees in specs:
        print(f"  → {key} : sujet='{sujet[:60]}'")
        try:
            svg = _extract_svg(gemini_call(DIAGRAM_PROMPT.format(sujet=sujet, donnees=donnees), max_tokens=1200).strip())
            diagrams[key] = svg if svg else ""
            print(f"    {'OK' if svg else 'VIDE — pas de SVG retourné'}")
        except Exception as e:
            print(f"    ERREUR : {e}")
            diagrams[key] = ""

    return diagrams


# ─────────────────────────────────────────────────────────────────────────────
# QUIZ (GitHub Pages)
# ─────────────────────────────────────────────────────────────────────────────

QUIZ_PROMPT = """À partir du contenu de cette newsletter, génère un quiz de 4 questions pour vérifier
la compréhension. Chaque question doit tester une notion clé abordée dans le numéro.

Format attendu — JSON strict :
{{
  "questions": [
    {{
      "question": "...",
      "options": ["A. ...", "B. ...", "C. ...", "D. ..."],
      "correct": 0,
      "explanation": "Explication détaillée de la bonne réponse et pourquoi les autres sont fausses."
    }}
  ]
}}

Contexte newsletter :
{newsletter_summary}
"""

def generate_quiz(content: dict) -> list:
    """Génère 4 questions QCM à partir du contenu de la newsletter."""
    summary = f"""
Deal : {content.get('ma_titre', '')}
{content.get('ma_contenu', '')[:600]}

Cours : {content.get('rappel_cours', '')[:800]}

Macro : {content.get('macro_titre', '')}
{content.get('macro_contenu', '')[:400]}
"""
    text = gemini_call(QUIZ_PROMPT.format(newsletter_summary=summary), max_tokens=2000)
    text = re.sub(r"```json\s*", "", text); text = re.sub(r"```\s*", "", text)
    start, end = text.find("{"), text.rfind("}") + 1
    try:
        return json.loads(text[start:end])["questions"]
    except (json.JSONDecodeError, ValueError, KeyError):
        return []


def render_quiz_page(questions: list, date_str: str, numero: str) -> str:
    """Génère la page HTML du quiz hébergée sur GitHub Pages."""
    q_js = json.dumps(questions, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Quiz — The Deal Brief N°{numero}</title>
  <style>
    body {{ font-family: 'Helvetica Neue', Arial, sans-serif; background: #fdf6ee; color: #2b1a0e;
           margin: 0; padding: 40px 20px; }}
    .container {{ max-width: 640px; margin: 0 auto; }}
    h1 {{ font-size: 24px; color: #e85d1a; margin-bottom: 4px; }}
    .subtitle {{ color: #7a5c45; font-size: 13px; margin-bottom: 40px; }}
    .question {{ background: #fff; border-radius: 8px; padding: 24px; margin-bottom: 20px;
                 box-shadow: 0 2px 8px rgba(232,93,26,0.08); }}
    .question h3 {{ font-size: 16px; margin-bottom: 16px; line-height: 1.5; }}
    .option {{ display: block; width: 100%; text-align: left; background: #fff8f2;
               border: 1px solid #fde0c5; border-radius: 6px; padding: 12px 16px;
               margin-bottom: 8px; cursor: pointer; font-size: 14px; transition: all .15s; }}
    .option:hover {{ background: #fff3e8; border-color: #f9a06b; }}
    .option.correct {{ background: #e6f9ec; border-color: #2ecc71; color: #1a6b3a; }}
    .option.wrong   {{ background: #fdecea; border-color: #e74c3c; color: #7b1c1c; }}
    .explanation {{ display: none; margin-top: 12px; padding: 12px 16px; background: #fff3e8;
                    border-left: 3px solid #e85d1a; font-size: 13px; color: #5a3520;
                    border-radius: 0 6px 6px 0; line-height: 1.6; }}
    .score {{ display: none; text-align: center; padding: 32px; background: #fff;
              border-radius: 8px; box-shadow: 0 2px 8px rgba(232,93,26,0.08); }}
    .score h2 {{ font-size: 28px; color: #e85d1a; }}
    .score p {{ color: #5a3520; }}
    #submit {{ display: block; width: 100%; padding: 16px; background: #e85d1a; color: #fff;
               border: none; border-radius: 8px; font-size: 16px; cursor: pointer; margin-top: 8px; }}
    #submit:hover {{ background: #c94e0e; }}
  </style>
</head>
<body>
<div class="container">
  <h1>Quiz — N°{numero}</h1>
  <p class="subtitle">The Deal Brief · {date_str} · 4 questions</p>
  <div id="quiz"></div>
  <button id="submit" onclick="submitQuiz()">Voir mes résultats</button>
  <div class="score" id="score"></div>
</div>
<script>
const questions = {q_js};
let answered = {{}};

function buildQuiz() {{
  const quiz = document.getElementById('quiz');
  questions.forEach((q, qi) => {{
    const div = document.createElement('div');
    div.className = 'question';
    div.innerHTML = `<h3>${{qi+1}}. ${{q.question}}</h3>` +
      q.options.map((o, oi) =>
        `<button class="option" id="q${{qi}}_${{oi}}" onclick="answer(${{qi}},${{oi}},${{q.correct}})">${{o}}</button>`
      ).join('') +
      `<div class="explanation" id="exp${{qi}}">${{q.explanation}}</div>`;
    quiz.appendChild(div);
  }});
}}

function answer(qi, oi, correct) {{
  if (answered[qi] !== undefined) return;
  answered[qi] = oi;
  const btn = document.getElementById(`q${{qi}}_${{oi}}`);
  const correctBtn = document.getElementById(`q${{qi}}_${{correct}}`);
  btn.classList.add(oi === correct ? 'correct' : 'wrong');
  if (oi !== correct) correctBtn.classList.add('correct');
  document.getElementById(`exp${{qi}}`).style.display = 'block';
}}

function submitQuiz() {{
  const score = Object.values(answered).filter((a, i) => a === questions[i].correct).length;
  const total = questions.length;
  const msg = score === total ? "🏆 Parfait ! Tu maîtrises ce numéro." :
              score >= total/2 ? "👍 Bien, relis les explications des questions ratées." :
              "📖 Relis le cours — ces notions vont revenir en entretien.";
  document.getElementById('score').innerHTML =
    `<h2>${{score}} / ${{total}}</h2><p>${{msg}}</p>`;
  document.getElementById('score').style.display = 'block';
  document.getElementById('submit').style.display = 'none';
  window.scrollTo(0, document.getElementById('score').offsetTop - 20);
}}

buildQuiz();
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# ANKI
# ─────────────────────────────────────────────────────────────────────────────

ANKI_DECK_ID  = 1234567890   # ID fixe pour que les imports s'ajoutent au même deck
ANKI_MODEL_ID = 9876543210

ANKI_MODEL = genanki.Model(
    ANKI_MODEL_ID,
    "The Deal Brief",
    fields=[{"name": "Recto"}, {"name": "Verso"}, {"name": "Numéro"}],
    templates=[{
        "name": "Card",
        "qfmt": "<div style='font-family:Georgia;font-size:18px;color:#2b1a0e;padding:20px'>{{Recto}}</div>",
        "afmt": """<div style='font-family:Georgia;font-size:18px;color:#2b1a0e;padding:20px'>
                   {{Recto}}<hr style='border-color:#fde0c5'>
                   <div style='color:#5a3520'>{{Verso}}</div>
                   <div style='font-size:11px;color:#f9a06b;margin-top:12px'>The Deal Brief {{Numéro}}</div>
                   </div>""",
    }],
    css="body{background:#fdf6ee}"
)

ANKI_PROMPT = """À partir du contenu de cette newsletter, génère 6 flashcards Anki.

RÈGLES :
- Les cartes portent sur des CONCEPTS, MÉCANIQUES et RAISONNEMENTS — jamais sur des chiffres spécifiques à un deal.
- Bons rectos : "Pourquoi un LBO amplifie-t-il le rendement des fonds propres ?", "Qu'est-ce que le goodwill ?", "Différence entre EV et equity value ?", "Quand utilise-t-on une dette mezzanine ?"
- Mauvais rectos (à éviter) : "Quel est le montant de la dette dans le deal X ?", "À quel prix a été racheté Y ?"
- Le verso explique le mécanisme en 2-4 phrases, avec un exemple générique si utile.
- Répartition : 2 cartes définition (qu'est-ce que X), 2 cartes mécanique (comment fonctionne X), 2 cartes raisonnement d'entretien (pourquoi / dans quel cas).

Retourne UNIQUEMENT ce JSON :
{{
  "cards": [
    {{"recto": "Question conceptuelle", "verso": "Explication du mécanisme (2-4 phrases)"}},
    ...
  ]
}}

Contexte newsletter :
{newsletter_summary}
"""

def generate_anki_cards(content: dict) -> list:
    summary = (
        f"Deal : {content.get('ma_titre','')}. {content.get('ma_contenu','')[:500]}\n"
        f"Cours : {content.get('rappel_cours','')[:700]}\n"
        f"Macro : {content.get('macro_contenu','')[:300]}"
    )
    text = gemini_call(ANKI_PROMPT.format(newsletter_summary=summary), max_tokens=2000)
    text = re.sub(r"```json\s*", "", text); text = re.sub(r"```\s*", "", text)
    start, end = text.find("{"), text.rfind("}") + 1
    try:
        return json.loads(text[start:end])["cards"]
    except (json.JSONDecodeError, ValueError, KeyError):
        return []


def build_anki_deck(new_cards: list, numero: str, deck_path: Path) -> Path:
    """Ajoute les nouvelles cartes au deck cumulatif et sauvegarde le .apkg."""
    deck = genanki.Deck(ANKI_DECK_ID, "The Deal Brief — M&A & Finance")
    # Charge les cartes existantes depuis un fichier JSON (les .apkg ne sont pas relisables)
    cards_json = deck_path.parent / "anki_cards.json"
    all_cards = json.loads(cards_json.read_text(encoding="utf-8")) if cards_json.exists() else []
    for c in new_cards:
        all_cards.append({**c, "numero": numero, "id": random.randrange(1 << 30, 1 << 31)})
    cards_json.write_text(json.dumps(all_cards, ensure_ascii=False, indent=2), encoding="utf-8")

    for c in all_cards:
        deck.add_note(genanki.Note(
            model=ANKI_MODEL,
            fields=[c["recto"], c["verso"], c["numero"]],
            guid=c["id"]
        ))
    genanki.Package(deck).write_to_file(str(deck_path))
    return deck_path


# ─────────────────────────────────────────────────────────────────────────────
# CONTEXTE CLAUDE PROJECT
# ─────────────────────────────────────────────────────────────────────────────

def generate_claude_context(content: dict, level: dict, numero: str, date_str: str) -> str:
    """Génère le fichier de contexte hebdomadaire à coller dans le Claude Project."""
    concepts = ", ".join(level["concepts_vus"][-6:]) if level["concepts_vus"] else "aucun encore"
    deals    = ", ".join(level["deals_ouverts"]) if level["deals_ouverts"] else "aucun en cours"
    return f"""# Contexte The Deal Brief — Mise à jour N°{numero} ({date_str})

## Mon profil
Étudiant préparant des entretiens en banque d'affaires M&A.
Objectif : {level['objectif']}
Niveau technique actuel : {level['depth']}/10

## Concepts déjà couverts dans la newsletter
{concepts}

## Deals suivis en ce moment
{deals}

## Contenu du dernier numéro ({date_str})

### Deal de la semaine
{content.get('ma_titre', '')}
{content.get('ma_contenu', '')[:1000]}

### Cours
{content.get('rappel_cours', '')[:1200]}

### Macro
{content.get('macro_titre', '')}
{content.get('macro_contenu', '')[:500]}

---
Tu es mon tuteur M&A. Quand je te pose une question :
- Pars toujours des deals et concepts qu'on a déjà couverts ensemble
- Adapte le niveau technique à {level['depth']}/10 (monte progressivement)
- Donne des réponses formulables en entretien, avec les bons termes
- Si je me trompe sur un concept, corrige avec un exemple chiffré
"""


# ─────────────────────────────────────────────────────────────────────────────
# RENDER & SEND
# ─────────────────────────────────────────────────────────────────────────────

def render_html(content: dict, template_path: Path, quiz_url: str = "") -> str:
    """Injecte le contenu dans le template HTML."""
    import re
    html = template_path.read_text(encoding="utf-8")
    data = {**content, "quiz_url": quiz_url}

    # Blocs conditionnels {{#key}}...{{/key}} — affichés seulement si valeur non vide
    def replace_block(m):
        key, inner = m.group(1), m.group(2)
        val = data.get(key, "")
        return inner.replace(f"{{{{{key}}}}}", str(val)) if val else ""
    html = re.sub(r"\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}", replace_block, html, flags=re.DOTALL)

    # Variables simples {{key}}
    for key, value in data.items():
        if isinstance(value, list):
            items = "\n".join(f'<li>{s}</li>' for s in value)
            html = html.replace(f"{{{{{key}}}}}", items)
        else:
            html = html.replace(f"{{{{{key}}}}}", str(value))
    return html


def send_email(html_body: str, subject: str, attachments: list[Path] = None):
    """Envoie la newsletter via Gmail SMTP avec pièces jointes optionnelles."""
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECIPIENT_EMAIL
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    for path in (attachments or []):
        if path.exists():
            part = MIMEBase("application", "octet-stream")
            part.set_payload(path.read_bytes())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{path.name}"')
            msg.attach(part)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, GMAIL_APP_PASS)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
    print(f"✅ Envoyé à {RECIPIENT_EMAIL}")


# ─────────────────────────────────────────────────────────────────────────────
# MISE À JOUR DU NIVEAU (appelée par Claude après génération)
# ─────────────────────────────────────────────────────────────────────────────

LEVEL_UPDATE_PROMPT = """Tu viens de générer ce numéro de newsletter. Mets à jour le profil de niveau du lecteur.

Profil actuel :
{level}

Contenu du numéro :
- Concepts enseignés : {cours_titre}
- Deal suivi : {deal_titre}
- Numéro : {numero}

Retourne UNIQUEMENT ce JSON mis à jour (même structure, valeurs mises à jour) :
{{
  "numero": {numero_int},
  "depth": <entre 1 et 10, augmente très progressivement>,
  "concepts_vus": <liste mise à jour avec les nouveaux concepts>,
  "deals_ouverts": <liste mise à jour — retire les deals clôturés, ajoute les nouveaux>,
  "objectif": "{objectif}",
  "trainy_index": {trainy_index}
}}
"""

def update_level(content: dict, level: dict, weekday: int) -> dict:
    numero = int(content.get("numero", level["numero"] + 1))
    # On avance dans le programme TRAINY chaque jour (rythme quotidien)
    current_idx = level.get("trainy_index", 0)
    new_idx = current_idx + 1

    text = gemini_call(LEVEL_UPDATE_PROMPT.format(
        level=json.dumps(level, ensure_ascii=False),
        cours_titre=content.get("rappel_cours", "")[:100],
        deal_titre=content.get("ma_titre", ""),
        numero=numero,
        numero_int=numero,
        objectif=level["objectif"],
        trainy_index=new_idx,
    ), max_tokens=500)
    start, end = text.find("{"), text.rfind("}") + 1
    try:
        result = json.loads(text[start:end])
    except (json.JSONDecodeError, ValueError):
        # Fallback : on garde le niveau actuel et on avance juste l'index
        result = {**level, "numero": numero, "trainy_index": new_idx}
    result.setdefault("trainy_index", new_idx)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    today    = datetime.date.today()
    date_str = today.strftime("%d %B %Y")
    weekday  = today.weekday()
    jour     = DAY_FORMAT.get(weekday, "")

    root        = Path(__file__).parent
    archive_dir = root / "archives"
    quiz_dir    = root / "quiz"        # GitHub Pages sert depuis la racine
    archive_dir.mkdir(exist_ok=True)
    quiz_dir.mkdir(exist_ok=True)

    genai.configure(api_key=GEMINI_KEY)
    template = root / "template.html"
    level    = load_level()

    # 1. Génération du contenu principal
    print(f"📝 [{jour}] Génération du contenu pour le {date_str}...")
    content = generate_content(date_str, archive_dir, weekday, level)
    numero  = content.get("numero", "XX")

    # 2. Schémas SVG (deal + cours + macro)
    print("📊 Génération des schémas...")
    diagrams = generate_diagrams(content)
    content.update(diagrams)

    # 3. Quiz (GitHub Pages)
    print("❓ Génération du quiz...")
    questions = generate_quiz(content)
    quiz_html = render_quiz_page(questions, date_str, numero)
    quiz_file = quiz_dir / f"quiz_{today.strftime('%Y-%m-%d')}.html"
    quiz_dir.mkdir(exist_ok=True)
    quiz_file.write_text(quiz_html, encoding="utf-8")
    quiz_url  = f"https://abarisan.github.io/newsletter-mna/quiz/quiz_{today.strftime('%Y-%m-%d')}.html"

    # 4. Anki deck cumulatif
    print("🎴 Génération des flashcards Anki...")
    anki_cards = generate_anki_cards(content)
    anki_path  = archive_dir / "the_deal_brief.apkg"
    build_anki_deck(anki_cards, numero, anki_path)

    # 5. Contexte Claude Project
    print("🤖 Génération du contexte Claude Project...")
    claude_ctx      = generate_claude_context(content, level, numero, date_str)
    ctx_file        = root / "claude_project_context.md"
    ctx_file.write_text(claude_ctx, encoding="utf-8")

    # 6. Mise à jour du niveau
    print("📈 Mise à jour du niveau...")
    new_level = update_level(content, level, weekday)
    save_level(new_level)

    # 7. Rendu HTML et archive
    print("🎨 Rendu HTML...")
    html         = render_html(content, template, quiz_url)
    archive_file = archive_dir / f"newsletter_{today.strftime('%Y-%m-%d')}.html"
    archive_file.write_text(html, encoding="utf-8")

    # 8. Envoi email avec Anki en pièce jointe
    lesson = get_lesson(level.get("trainy_index", 0))
    subject_prefix = f"📚 M{lesson['module']}·{lesson['video']} {lesson['titre'][:40]}"
    print("📧 Envoi par email...")
    send_email(html, f"{subject_prefix} — The Deal Brief N°{numero} · {date_str}",
               attachments=[anki_path])

    print(f"✅ Terminé — N°{numero} | Niveau {new_level['depth']}/10")


if __name__ == "__main__":
    main()
