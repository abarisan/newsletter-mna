"""
Newsletter M&A · Finance · IA · Géopolitique
Génère le contenu via Claude API + envoie par email chaque vendredi.
"""

import anthropic
import smtplib
import os
import json
import datetime
import genanki
import random
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

# Rythme : lundi = deal, mercredi = cours, vendredi = macro + question
DAY_FORMAT = {
    0: "LUNDI",    # Monday
    2: "MERCREDI", # Wednesday
    4: "VENDREDI", # Friday
}


RECIPIENT_EMAIL = "sooriyakumar.abarisan@gmail.com"
SENDER_EMAIL    = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASS  = os.environ["GMAIL_APP_PASSWORD"]
ANTHROPIC_KEY   = os.environ["ANTHROPIC_API_KEY"]


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

**Règles absolues :**
- Langue : français, ton direct et pédagogique, jamais condescendant
- Chiffres précis, sources nommées (Bloomberg, FT, CreditSights, SEC, Mergermarket...)
- Jamais de généralités : toujours un acteur nommé, un chiffre, une date
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
  "sources": ["..."]
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
  "sources": ["..."]
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
  "sources": ["..."]
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
  "sources": ["Bloomberg — titre article", "FT — titre article", ...]
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
    """Retourne le prompt adapté au jour de la semaine."""
    if weekday == 0:
        return CONTENT_PROMPT_LUNDI
    elif weekday == 2:
        return CONTENT_PROMPT_MERCREDI
    elif weekday == 4:
        return CONTENT_PROMPT_VENDREDI
    else:
        return CONTENT_PROMPT  # fallback format complet


def generate_content(client: anthropic.Anthropic, date_str: str, archive_dir: Path, weekday: int) -> dict:
    """Appelle Claude pour générer le contenu de la newsletter."""
    import json

    numero          = get_next_issue_number(archive_dir)
    previous_issues = load_previous_issues(archive_dir)
    prompt_template = get_day_prompt(weekday)

    prompt = prompt_template.format(
        date=date_str,
        numero=numero,
        previous_issues=previous_issues
    )

    message = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=5000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )

    text = message.content[0].text
    start = text.find("{")
    end   = text.rfind("}") + 1
    return json.loads(text[start:end])


# ─────────────────────────────────────────────────────────────────────────────
# NIVEAU ADAPTATIF
# ─────────────────────────────────────────────────────────────────────────────

LEVEL_FILE = Path(__file__).parent / "level.json"

DEFAULT_LEVEL = {
    "numero": 0,
    "depth": 1,          # 1=débutant → 10=expert
    "concepts_vus": [],  # concepts déjà couverts
    "deals_ouverts": [], # deals à suivre
    "objectif": "Préparer des entretiens M&A dans 1 mois, puis sur 2-3 ans",
}

def load_level() -> dict:
    if LEVEL_FILE.exists():
        return json.loads(LEVEL_FILE.read_text(encoding="utf-8"))
    return DEFAULT_LEVEL.copy()

def save_level(level: dict):
    LEVEL_FILE.write_text(json.dumps(level, ensure_ascii=False, indent=2), encoding="utf-8")


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

def generate_quiz(client: anthropic.Anthropic, content: dict) -> list:
    """Génère 4 questions QCM à partir du contenu de la newsletter."""
    summary = f"""
Deal : {content.get('ma_titre', '')}
{content.get('ma_contenu', '')[:600]}

Cours : {content.get('rappel_cours', '')[:800]}

Macro : {content.get('macro_titre', '')}
{content.get('macro_contenu', '')[:400]}
"""
    msg = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=2000,
        messages=[{"role": "user", "content": QUIZ_PROMPT.format(newsletter_summary=summary)}]
    )
    text = msg.content[0].text
    start, end = text.find("{"), text.rfind("}") + 1
    return json.loads(text[start:end])["questions"]


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
Mélange : définitions, mécaniques chiffrées, raisonnements d'entretien, faits précis sur le deal.
Les cartes doivent être progressives : certaines basiques, d'autres plus techniques.

Retourne UNIQUEMENT ce JSON :
{{
  "cards": [
    {{"recto": "Question ou concept au recto", "verso": "Réponse complète au verso (2-4 phrases, chiffres si pertinent)"}},
    ...
  ]
}}

Contexte newsletter :
{newsletter_summary}
"""

def generate_anki_cards(client: anthropic.Anthropic, content: dict) -> list:
    summary = (
        f"Deal : {content.get('ma_titre','')}. {content.get('ma_contenu','')[:500]}\n"
        f"Cours : {content.get('rappel_cours','')[:700]}\n"
        f"Macro : {content.get('macro_contenu','')[:300]}"
    )
    msg = client.messages.create(
        model="claude-opus-4-8", max_tokens=2000,
        messages=[{"role": "user", "content": ANKI_PROMPT.format(newsletter_summary=summary)}]
    )
    text = msg.content[0].text
    start, end = text.find("{"), text.rfind("}") + 1
    return json.loads(text[start:end])["cards"]


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
    html = template_path.read_text(encoding="utf-8")
    content_with_extras = {**content, "quiz_url": quiz_url}
    for key, value in content_with_extras.items():
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
  "objectif": "{objectif}"
}}
"""

def update_level(client: anthropic.Anthropic, content: dict, level: dict) -> dict:
    numero = int(content.get("numero", level["numero"] + 1))
    msg = client.messages.create(
        model="claude-opus-4-8", max_tokens=500,
        messages=[{"role": "user", "content": LEVEL_UPDATE_PROMPT.format(
            level=json.dumps(level, ensure_ascii=False),
            cours_titre=content.get("rappel_cours", "")[:100],
            deal_titre=content.get("ma_titre", ""),
            numero=numero,
            numero_int=numero,
            objectif=level["objectif"]
        )}]
    )
    text = msg.content[0].text
    start, end = text.find("{"), text.rfind("}") + 1
    return json.loads(text[start:end])


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
    quiz_dir    = root / "docs"        # GitHub Pages sert le dossier /docs
    archive_dir.mkdir(exist_ok=True)
    quiz_dir.mkdir(exist_ok=True)

    client   = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    template = root / "template.html"
    level    = load_level()

    # 1. Génération du contenu principal
    print(f"📝 [{jour}] Génération du contenu pour le {date_str}...")
    content = generate_content(client, date_str, archive_dir, weekday)
    numero  = content.get("numero", "XX")

    # 2. Quiz (GitHub Pages)
    print("❓ Génération du quiz...")
    questions = generate_quiz(client, content)
    quiz_html = render_quiz_page(questions, date_str, numero)
    quiz_file = quiz_dir / f"quiz_{today.strftime('%Y-%m-%d')}.html"
    quiz_file.write_text(quiz_html, encoding="utf-8")
    quiz_url  = f"https://abarisan.github.io/newsletter-mna/quiz_{today.strftime('%Y-%m-%d')}.html"

    # 3. Anki deck cumulatif
    print("🎴 Génération des flashcards Anki...")
    anki_cards = generate_anki_cards(client, content)
    anki_path  = archive_dir / "the_deal_brief.apkg"
    build_anki_deck(anki_cards, numero, anki_path)

    # 4. Contexte Claude Project
    print("🤖 Génération du contexte Claude Project...")
    claude_ctx      = generate_claude_context(content, level, numero, date_str)
    ctx_file        = root / "claude_project_context.md"
    ctx_file.write_text(claude_ctx, encoding="utf-8")

    # 5. Mise à jour du niveau
    print("📈 Mise à jour du niveau...")
    new_level = update_level(client, content, level)
    save_level(new_level)

    # 6. Rendu HTML et archive
    print("🎨 Rendu HTML...")
    html         = render_html(content, template, quiz_url)
    archive_file = archive_dir / f"newsletter_{today.strftime('%Y-%m-%d')}.html"
    archive_file.write_text(html, encoding="utf-8")

    # 7. Envoi email avec Anki en pièce jointe
    subject_prefix = {"LUNDI": "📌 Deal", "MERCREDI": "📚 Cours", "VENDREDI": "🌍 Macro"}.get(jour, "📰")
    print("📧 Envoi par email...")
    send_email(html, f"{subject_prefix} — The Deal Brief N°{numero} · {date_str}",
               attachments=[anki_path])

    print(f"✅ Terminé — N°{numero} | Niveau {new_level['depth']}/10")


if __name__ == "__main__":
    main()
