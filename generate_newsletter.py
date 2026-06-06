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
préparant des entretiens en banque d'affaires (M&A). Ton objectif : lui faire comprendre la finance
en profondeur, pas juste lister des actu sans contexte.

Règles absolues :
- Explique TOUJOURS le contexte et les mécanismes derrière chaque info
- Cite les sources (Bloomberg, FT, Reuters, PwC, BCG, S&P Global, Mergermarket...)
- Inclus un rappel de cours à la fin avec les notions complexes utilisées
- Langue : français, ton professionnel mais pédagogique
- Structure : respecte exactement le format HTML fourni
"""

CONTENT_PROMPT = """Génère le contenu complet pour la newsletter THE DEAL BRIEF de cette semaine ({date}).

## Philosophie éditoriale — à respecter absolument

**Moins, mais mieux.** Tu ne fais pas un agrégateur d'actu. Tu choisis avec exigence :
- 1 seul deal M&A, le plus instructif de la semaine (pas forcément le plus grand)
- 1 seul signal macro ou géopo vraiment significatif
- 1 seul sujet IA s'il est directement lié à la finance ou au M&A
- Le rappel de cours approfondit UN concept qui revient dans l'actu récente — et peut
  reprendre un thème d'un numéro précédent pour aller plus loin (ex : N°1 = mécanique LBO,
  N°2 = comment modéliser un LBO, N°3 = les covenants de dette dans un LBO)

**Progression d'un numéro à l'autre.** Chaque rappel de cours doit s'inscrire dans un arc
pédagogique cohérent sur plusieurs semaines. Indique toujours en intro du rappel si c'est
la suite d'un sujet précédent et ce que le lecteur doit déjà savoir.

## Structure du numéro

1. **DEAL DE LA SEMAINE**
   - 1 deal réel, récent, nommé et chiffré (acquéreur, cible, prix, prime, levier, banques)
   - Rationnel stratégique côté acquéreur ET côté cible
   - Statut réglementaire si pertinent
   - 1 phrase clé à sortir en entretien, formulée et prête à l'emploi

2. **SIGNAL MACRO / GÉOPOLITIQUE**
   - 1 donnée ou événement qui change vraiment quelque chose pour les marchés ou le M&A
   - Explication du mécanisme de transmission (comment ça impacte concrètement les deals ?)

3. **IA & FINANCE** (uniquement si un fait marquant cette semaine, sinon à sauter)
   - 1 mouvement stratégique IA avec impact direct sur les valorisations ou les deals tech

4. **RAPPEL DE COURS — 1 sujet, en profondeur**
   - Principe de base → mécanique chiffrée → analogie concrète → lien avec le deal du numéro
   - Arc progressif : chaque numéro va plus loin que le précédent sur le même grand thème

5. **QUESTION D'ENTRETIEN**
   - 1 question en lien direct avec le contenu de CE numéro, avec structure de réponse

Retourne UNIQUEMENT le contenu JSON structuré ainsi :
{{
  "numero": "XX",
  "date": "{date}",
  "ma_titre": "...",
  "ma_contenu": "HTML...",
  "macro_titre": "...",
  "macro_contenu": "HTML...",
  "ia_titre": "...",
  "ia_contenu": "HTML... ou vide si rien de pertinent",
  "rappel_cours": "HTML...",
  "question_entretien": "...",
  "reponse_structuree": "HTML...",
  "sources": ["source1", "source2", ...]
}}
"""


def generate_content(client: anthropic.Anthropic, date_str: str) -> dict:
    """Appelle Claude pour générer le contenu de la newsletter."""
    import json

    message = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": CONTENT_PROMPT.format(date=date_str)}
        ]
    )

    text = message.content[0].text
    # Extraire le JSON de la réponse
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
    content = generate_content(client, date_str)

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
