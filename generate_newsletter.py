"""
Newsletter M&A · Finance · IA · Géopolitique
Génère le contenu via Claude API + envoie par email chaque vendredi.
"""

import anthropic
import smtplib
import os
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path


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


def generate_content(client: anthropic.Anthropic, date_str: str, archive_dir: Path) -> dict:
    """Appelle Claude pour générer le contenu de la newsletter."""
    import json

    numero          = get_next_issue_number(archive_dir)
    previous_issues = load_previous_issues(archive_dir)

    prompt = CONTENT_PROMPT.format(
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


def render_html(content: dict, template_path: Path) -> str:
    """Injecte le contenu dans le template HTML."""
    html = template_path.read_text(encoding="utf-8")
    for key, value in content.items():
        if isinstance(value, list):
            # Sources : liste → items HTML
            items = "\n".join(f'<li>{s}</li>' for s in value)
            html = html.replace(f"{{{{{key}}}}}", items)
        else:
            html = html.replace(f"{{{{{key}}}}}", str(value))
    return html


def send_email(html_body: str, date_str: str):
    """Envoie la newsletter via Gmail SMTP."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"📊 The Deal Brief — {date_str}"
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECIPIENT_EMAIL

    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, GMAIL_APP_PASS)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())

    print(f"✅ Newsletter envoyée à {RECIPIENT_EMAIL}")


def main():
    today    = datetime.date.today()
    date_str = today.strftime("%d %B %Y")

    client   = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    template = Path(__file__).parent / "template.html"

    print(f"📝 Génération du contenu pour le {date_str}...")
    content = generate_content(client, date_str, archive_dir)

    print("🎨 Rendu HTML...")
    html = render_html(content, template)

    # Sauvegarde locale (archive)
    archive_dir = Path(__file__).parent / "archives"
    archive_dir.mkdir(exist_ok=True)
    archive_file = archive_dir / f"newsletter_{today.strftime('%Y-%m-%d')}.html"
    archive_file.write_text(html, encoding="utf-8")
    print(f"💾 Archivée : {archive_file}")

    print("📧 Envoi par email...")
    send_email(html, date_str)


if __name__ == "__main__":
    main()
