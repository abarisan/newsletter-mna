"""
Édition Spéciale The Deal Brief — articles IESE + MSCI
"""
from groq import Groq
import smtplib
import os
import re
import json
import datetime
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

RECIPIENT_EMAIL = "sooriyakumar.abarisan@gmail.com"
SENDER_EMAIL    = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASS  = os.environ["GMAIL_APP_PASSWORD"]
GROQ_KEY        = os.environ["GROQ_API_KEY"]

ARTICLE_1 = """
ARTICLE 1 — IESE Insight : "How institutional investors changed governance mechanisms around the world"

Thèse : Les investisseurs institutionnels (BlackRock, Vanguard, State Street) sont devenus les arbitres de la gouvernance mondiale.

Points clés :
- Ces 3 géants figurent dans le top 5 des actionnaires de 90% des sociétés du S&P 500
- Leur montée en puissance a produit des effets mesurables : conseils plus indépendants, moins de mesures anti-OPA, divulgations plus transparentes, dividendes en hausse
- Les fonds passifs (ETF) n'ont aucune incitation à "battre l'indice" mais améliorent quand même la gouvernance
- Ils soutiennent la consolidation sectorielle plutôt que la discipline managériale — favorisant les marges globales plutôt que la concurrence
- Les militants activistes gagnent leurs batailles uniquement quand ces géants passifs les soutiennent
- Variations géographiques : domination institutionnelle aux US, familles encore en contrôle en Asie, Europe en transition
- Question ouverte : leur orientation vers les versements aux actionnaires favorise-t-elle vraiment la dynamique économique durable ?
"""

ARTICLE_2 = """
ARTICLE 2 — MSCI Blog : "How Megacap IPOs in 2026 Could Reshape Global Benchmarks"

Thèse : Une vague d'IPO de méga-capitalisations en 2026 (dont SpaceX ~200 Md$) va restructurer les indices MSCI et forcer des milliards de réallocations.

Points clés :
- MSCI modélise l'entrée des 10 plus grandes sociétés VC-backed, valorisées entre 50 Md$ et 1 000 Md$ (SpaceX)
- Secteurs concernés : logiciels IA, fintech, aérospatiale/défense
- La part des US dans le MSCI ACWI IMI passerait de 61,75% à 62,78% (scénario flottant 95%)
- Entrées IPO estimées : 19 Md$ dans le scénario flottant 25%
- Turnover MSCI USA IMI : normalement 1,16%, monte jusqu'à 3,34% dans l'industriel
- Pour un portefeuille de 100M$ : 1,16M$ de rééquilibrage obligatoire
- 3 IPOs hypothétiques se classeraient directement dans le top 30 du MSCI ACWI IMI
- Rotation sectorielle : les semiconducteurs perdent du poids face aux plateformes applicatives
- Conseil MSCI : tester les portefeuilles sur plusieurs scénarios de flottant avant les IPOs
"""

PROMPT = f"""Génère une ÉDITION SPÉCIALE de The Deal Brief basée sur deux articles académiques/recherche.

{ARTICLE_1}

{ARTICLE_2}

## Format de l'édition spéciale — newsletter M&A pédagogique

Ces deux articles sont complémentaires :
- IESE montre comment les investisseurs institutionnels gouvernent les entreprises cotées
- MSCI montre comment les grandes IPOs de 2026 vont restructurer ces mêmes indices

### 1. ANALYSE IESE — Gouvernance institutionnelle (ma_contenu)
Résumé approfondi avec ce que ça signifie pour un banquier M&A :
- Quand tu conseilles un client sur une fusion, qui sont les vrais décideurs ?
- Comment BlackRock/Vanguard votent concrètement sur une transaction ?
- Ce qu'il faut retenir pour un entretien (avec les bons termes)

### 2. ANALYSE MSCI — IPOs méga-cap et indices (macro_contenu)
Résumé approfondi avec les implications pour le M&A et les marchés :
- Pourquoi une IPO SpaceX force des milliards de réallocations automatiques
- Comment fonctionnent les indices MSCI (constituants, flottant, rebalancement)
- Lien avec le travail des banquiers ECM (Equity Capital Markets)

### 3. COURS — Connexion entre les deux (rappel_cours)
Un cours structuré qui relie les deux articles :
- Quand SpaceX entre dans le MSCI, BlackRock/Vanguard doivent acheter mécaniquement
- Qui décide ensuite du vote en AG ? Quel impact sur la gouvernance ?
- Les mécanismes clés à retenir avec définitions encadrées

### 4. QUESTION D'ENTRETIEN
Une question qui connecte les deux articles. Réponse en 3 points.

Retourne UNIQUEMENT ce JSON :
{{
  "numero": "SPÉCIAL",
  "date": "{datetime.date.today().strftime('%d %B %Y')}",
  "jour": "Édition Spéciale",
  "ma_titre": "Gouvernance institutionnelle & IPOs méga-cap : deux articles à connaître",
  "ma_contenu": "HTML complet section IESE avec <p> <strong> <em> <ul> et class='callout' — MINIMUM 4 paragraphes",
  "macro_titre": "Comment les IPOs méga-cap de 2026 vont restructurer les indices MSCI",
  "macro_contenu": "HTML complet section MSCI — toujours rempli",
  "ia_titre": "",
  "ia_contenu": "",
  "rappel_cours": "HTML cours connectant les deux articles avec <div class='term'><div class='term-name'>TERME</div>définition</div> — MINIMUM 400 mots",
  "question_entretien": "Question précise connectant gouvernance institutionnelle et IPO/indices",
  "reponse_structuree": "HTML réponse en 3 points avec les bons termes",
  "sources": ["[N1] IESE Insight — How institutional investors changed governance mechanisms around the world", "[N2] MSCI Research — How Megacap IPOs in 2026 Could Reshape Global Benchmarks"]
}}
"""

def render_html(content: dict, template_path: Path) -> str:
    html = template_path.read_text(encoding="utf-8")
    data = {**content, "quiz_url": ""}

    def replace_block(m):
        key, inner = m.group(1), m.group(2)
        val = data.get(key, "")
        return inner.replace(f"{{{{{key}}}}}", str(val)) if val else ""
    html = re.sub(r"\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}", replace_block, html, flags=re.DOTALL)

    for key, value in data.items():
        if isinstance(value, list):
            items = "\n".join(f'<li>{s}</li>' for s in value)
            html = html.replace(f"{{{{{key}}}}}", items)
        else:
            html = html.replace(f"{{{{{key}}}}}", str(value))
    return html

def send_email(html_body: str, subject: str):
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = RECIPIENT_EMAIL
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, GMAIL_APP_PASS)
        server.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
    print(f"Envoye a {RECIPIENT_EMAIL}")

def main():
    client = Groq(api_key=GROQ_KEY)
    root   = Path(__file__).parent

    print("Generation edition speciale...")
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=8000,
        messages=[{"role": "user", "content": PROMPT}]
    )

    text = response.choices[0].message.content
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*", "", text)
    start, end = text.find("{"), text.rfind("}") + 1
    raw = text[start:end]
    raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', raw)
    content = json.loads(raw)
    content.update({"diagram_deal": "", "diagram_cours": "", "diagram_macro": ""})

    html = render_html(content, root / "template.html")
    date_str = datetime.date.today().strftime("%d %B %Y")
    send_email(html, f"📖 Edition Speciale — The Deal Brief · {date_str}")
    print("OK!")

if __name__ == "__main__":
    main()
