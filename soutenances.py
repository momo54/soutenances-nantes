#!/usr/bin/env python3
"""Soutenances de thèse (et HDR) À VENIR en informatique à Nantes.

Interroge en direct, à chaque lancement :
  1. Nantes Université – page « Soutenances de thèses » (section à venir) ;
     chaque fiche est lue pour obtenir discipline, labo, heure et salle.
  2. Agenda du LS2N (API WordPress publique de ls2n.fr) : thèses et HDR du labo.
  3. Centrale Nantes – page « PhD Defenses » (ED MaSTIC ou laboratoire LS2N).

« Informatique » = discipline contenant « informatique » OU laboratoire LS2N
(le LS2N inclut aussi automatique/robotique : la discipline est affichée).
Aucune dépendance : Python 3.8+.

Exemples :
  python3 soutenances.py                  # à venir, informatique / LS2N
  python3 soutenances.py --tout           # à venir, toutes disciplines (Nantes)
  python3 soutenances.py --depuis 15      # inclut aussi les 15 derniers jours
  python3 soutenances.py --html page.html # écrit aussi une page HTML
  python3 soutenances.py --json           # sortie JSON
"""

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

UA = "Mozilla/5.0 (soutenances-nantes script)"
NANTES_URL = "https://www.univ-nantes.fr/recherche-et-innovation/doctorat/soutenances-de-theses"
LS2N_API = "https://www.ls2n.fr/wp-json/wp/v2/agenda"
CENTRALE_URL = "https://research.ec-nantes.fr/en/phd-defenses"

MOIS_FR = {m: i for i, m in enumerate(
    ["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet",
     "aout", "septembre", "octobre", "novembre", "decembre"], 1)}
MOIS_EN = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], 1)}


# ------------------------------------------------------------------ outils
def get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def texte(fragment):
    t = re.sub(r"<br\s*/?>", ", ", fragment or "")
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"\s+", " ", html.unescape(t)).strip()
    return re.sub(r"\s+,", ",", t).strip(" ,")


def ascii_min(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def cle(s):
    return re.sub(r"[^a-z]", "", ascii_min(s))


def date_fr(s):
    m = re.search(r"(\d{1,2})(?:er)?\s+([A-Za-zéûÉÛ]+)\s+(\d{4})", s)
    if m and ascii_min(m.group(2)) in MOIS_FR:
        return dt.date(int(m.group(3)), MOIS_FR[ascii_min(m.group(2))], int(m.group(1)))
    return None


def date_en(s):
    m = re.search(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", s)
    if m and m.group(1).lower() in MOIS_EN:
        return dt.date(int(m.group(3)), MOIS_EN[m.group(1).lower()], int(m.group(2)))
    return None


def fiche(**kw):
    base = dict(date="", horaire="", type="Thèse", nom="", sujet="", discipline="",
                direction="", labo="", equipe="", lieu="", live="", lien="", source="")
    base.update(kw)
    return base


def _safe(f, *a):
    try:
        return f(*a)
    except Exception as e:  # une source ou une page cassée ne bloque pas le reste
        print(f"  ! {getattr(f, '__name__', f)}: {e}", file=sys.stderr)
        return None


def en_parallele(f, items):
    with ThreadPoolExecutor(max_workers=8) as ex:
        return [r for r in ex.map(lambda x: _safe(f, x), items) if r]


# --------------------------------------------------------- Nantes Université
def nantes_detail(item):
    url, nom, sujet, jour = item
    p = get(url)
    s = fiche(date=jour.isoformat(), nom=nom, sujet=sujet, lien=url, source="Nantes Université")
    m = re.search(r'class="dates__detail">\s*Le\s+([^<]+)<', p)
    if m and date_fr(m.group(1)):
        s["date"] = date_fr(m.group(1)).isoformat()
    m = re.search(r'class="dates__detail toolbox">\s*<div>(.*?)</div>', p, re.S)
    s["lieu"] = texte(m.group(1)) if m else ""
    m = re.search(r'actualite-dates--withoutstyle">\s*<div class="toolbox">\s*<strong>(.*?)</strong>', p, re.S)
    s["horaire"] = texte(m.group(1)) if m else ""
    m = re.search(r'<div id="resume"[^>]*>(.*?)</div>', p, re.S)
    resume = texte(m.group(1)) if m else ""
    m = re.search(r"doctorat en (.+?) de .+? sous la (?:co-?)?direction de (.+?)\.?$", resume)
    if m:
        s["discipline"], s["direction"] = m.group(1).strip(), m.group(2).strip()
    m = re.search(r'>Laboratoire</h2>.*?<a[^>]*>([^<]+)</a>', p, re.S)
    s["labo"] = texte(m.group(1)) if m else ""
    if re.search(r"habilitation", sujet + resume, re.I):
        s["type"] = "HDR"
    return s


def nantes(limite):
    page = get(NANTES_URL)
    motif = re.compile(
        r'<a href="([^"]+)" class="lien_interne">\s*(.+?)\s*</a>\s*</div>\s*'
        r'<div class="dates">\s*<time class="dates__debut">([^<]+)</time>', re.S)
    items, vus = [], set()
    for url, libelle, date_txt in motif.findall(page):
        jour = date_fr(date_txt)
        if not jour or jour < limite or url in vus:
            continue
        vus.add(url)
        libelle = texte(libelle)
        nom, _, sujet = libelle.partition(":")
        items.append((url, nom.strip(), sujet.strip().strip('"“”« »').rstrip("."), jour))
    return en_parallele(nantes_detail, items)


# -------------------------------------------------------------------- LS2N
def ls2n_detail(post):
    page = get(post["link"])
    titre = texte(post["title"]["rendered"])
    m = re.search(r"Date de l.{1,10}?vènement\s*:\s*</b>\s*([0-9]{2}/[0-9]{2}/[0-9]{4})", page)
    if not m:
        return None
    jour = dt.datetime.strptime(m.group(1), "%d/%m/%Y").date()
    h = re.search(r"Horaire\s*:\s*</b>\s*([^<]+)", page)
    cat = re.search(r"<h4>\s*\[([^\]]+)\]\s*</h4>", page)
    cat = texte(cat.group(1)) if cat else ""
    lieu = ""
    ml = re.search(r"Lieu\s*:\s*</b>(.*?)</ul>", page, re.S)
    if ml:
        items = [texte(x) for x in re.findall(r"<li>(.*?)</li>", ml.group(1), re.S)]
        lieu = " – ".join(i.replace("Site :", "").strip() for i in items if i)
    equipes = re.findall(r'class="bloc_equip_plateforme_lien"[^>]*>([^<]+)<', page)
    live = re.search(r"Lien Live\s*:\s*</b>\s*<a[^>]*href=\"([^\"]+)\"", page)
    sans_tag = re.sub(r"^\s*\[[^\]]+\]\s*:?\s*", "", titre)
    mt = re.match(r"(.+?)(?:\s+présente|\s*:|\s*«)", sans_tag)
    nom = mt.group(1).strip() if mt else ""
    if not nom or len(nom.split()) > 6:
        mn = re.search(r"soutenance (?:de thèse|d.HDR|de HDR) (?:de doctorat )?de\s*"
                       r"(?:</?strong>\s*)*([^,<]+?)(?:</strong>)?\s*[,<(]", page)
        nom = texte(mn.group(1)) if mn else ""
    nom = re.sub(r"^(?:M\.|Mr\.?|Mme\.?|Mrs\.?|Ms\.?|Dr\.?)\s+", "", nom)
    sujet = re.search(r"«\s*(.+?)\s*»", titre)
    if sujet:
        sujet = sujet.group(1)
    else:
        ms = re.search(r"présente ses travaux sur\s+(?:le thème\s+|la\s+|le\s+|les\s+|l['’]\s*)?(.+)", sans_tag)
        sujet = ms.group(1).rstrip(" .") if ms else sans_tag
        sujet = sujet[:1].upper() + sujet[1:]
    return fiche(
        date=jour.isoformat(), horaire=h.group(1).strip() if h else "",
        type="HDR" if ("HDR" in cat.upper() or "HDR" in titre.upper()) else "Thèse",
        nom=nom, sujet=sujet, labo="LS2N", equipe=", ".join(e.strip() for e in equipes),
        lieu=lieu, live=live.group(1) if live else "", lien=post["link"], source="LS2N")


def ls2n(limite):
    # une soutenance est annoncée quelques semaines avant : on regarde les posts récents
    apres = (min(limite, dt.date.today()) - dt.timedelta(days=150)).isoformat()
    params = {"search": "soutenance", "per_page": 100, "after": apres + "T00:00:00",
              "_fields": "id,date,link,title"}
    posts = json.loads(get(LS2N_API + "?" + urllib.parse.urlencode(params)))
    return [s for s in en_parallele(ls2n_detail, posts) if s["date"] >= limite.isoformat()]


# ---------------------------------------------------------------- Centrale
def centrale_detail(item):
    lien, nom, ed, jour, sujet = item
    p = re.sub(r"<script.*?</script>|<style.*?</style>", "", get(lien), flags=re.S)
    lignes = [l.strip() for l in html.unescape(re.sub(r"<[^>]+>", "\n", p)).split("\n") if l.strip()]
    brut = " | ".join(lignes)
    s = fiche(date=jour.isoformat(), nom=nom, sujet=sujet, lien=lien,
              source="Centrale Nantes", discipline="ED " + ed)
    m = re.search(r"\d{4} at ([0-9:]+\s*[ap]m)", brut)
    s["horaire"] = m.group(1) if m else ""
    m = re.search(r"\d{4} at [0-9:]+\s*[ap]m\s*(?:\|\s*)?(.+?)\s*PhD supervisor", brut)
    s["lieu"] = m.group(1).strip(" |") if m else "Centrale Nantes"
    m = re.search(r"PhD supervisor\s*:\s*(.+?)\s*Laboratory", brut)
    s["direction"] = m.group(1).strip(" |") if m else ""
    m = re.search(r"Laboratory\s*:\s*([A-Za-z0-9\-]+)", brut)
    s["labo"] = m.group(1) if m else ""
    return s


def centrale(limite, tout=False):
    page = get(CENTRALE_URL)
    motif = re.compile(
        r'<a href="([^"]+)"[^>]*>\s*PhD thesis defen[cs]e\s*-\s*(.+?)\s*-\s*ED\s+([A-Z]+)\s*</a>'
        r'.*?class="date--debut">([^<]+)<.*?class="resume">(.*?)</div>', re.S)
    items = []
    for lien, nom, ed, date_txt, resume in motif.findall(page):
        jour = date_en(date_txt)
        if jour and jour >= limite:
            items.append((lien, texte(nom), ed.upper(), jour, texte(resume)))
    res = en_parallele(centrale_detail, items)
    return res if tout else [s for s in res if s["discipline"] == "ED MASTIC" or s["labo"] == "LS2N"]


# ------------------------------------------------------------- traitement
def est_info(s):
    return "informatique" in ascii_min(s["discipline"]) or s["labo"].upper() == "LS2N" \
        or s["source"] == "LS2N" or s["discipline"] == "ED MASTIC"


def fusion(listes):
    """Fusionne les sources ; même date + même nom de famille (ou même sujet) = doublon."""
    vus, out = {}, []
    for s in (x for l in listes for x in l):
        cles = [(s["date"], "s:" + cle(s["sujet"])[:40])]
        if s["nom"]:
            cles.append((s["date"], "n:" + cle(s["nom"].split()[-1])))
        autre = next((vus[k] for k in cles if k in vus), None)
        for k in cles:
            vus.setdefault(k, autre or s)
        if autre:
            for champ in ("horaire", "lieu", "equipe", "labo", "discipline", "direction", "live"):
                autre[champ] = autre[champ] or s[champ]
            autre["source"] += " + " + s["source"]
            continue
        out.append(s)
    return sorted(out, key=lambda s: (s["date"], minutes(s["horaire"])))


def minutes(h):
    """« à 14 heures », « 9h30 », « 10:30 à 13:30 », « 3:00pm » -> minutes depuis minuit."""
    m = re.search(r"(\d{1,2})\s*(?:h|:|heures?)\s*(\d{2})?\s*([ap]m)?", h or "", re.I)
    if not m:
        return 24 * 60
    hh = int(m.group(1)) % 12 + (12 if (m.group(3) or "").lower() == "pm" else 0) \
        if m.group(3) else int(m.group(1))
    return hh * 60 + int(m.group(2) or 0)


JOURS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]


def affiche(liste):
    if not liste:
        print("Aucune soutenance trouvée pour cette période.")
        return
    for s in liste:
        d = dt.date.fromisoformat(s["date"])
        entete = f"{JOURS[d.weekday()]} {d.strftime('%d/%m/%Y')}"
        if s["horaire"]:
            entete += f"  {s['horaire']}"
        print(f"\n{entete}  [{s['type']}]  {s['nom']}")
        print(f"   « {s['sujet']} »")
        info = [s["discipline"], s["direction"] and "dir. " + s["direction"],
                s["labo"] + (f" / {s['equipe']}" if s["equipe"] else "")]
        print("   " + " | ".join(x for x in info if x))
        if s["lieu"]:
            print(f"   {s['lieu']}")
        if s["live"]:
            print(f"   Live : {s['live']}")
        print(f"   {s['lien']}  ({s['source']})")
    print()


def page_html(liste, chemin, avec_bascule=False):
    """Page HTML. Avec avec_bascule, `liste` contient toutes les disciplines et une case
    à cocher permet d'afficher les non-informatiques (masquées par défaut)."""
    e = html.escape
    lignes = []
    for s in liste:
        d = dt.date.fromisoformat(s["date"])
        live = f' · <a href="{e(s["live"])}">live</a>' if s["live"] else ""
        labo = s["labo"] + (f" / {s['equipe']}" if s["equipe"] else "")
        cls = "" if est_info(s) else ' class="autre"'
        lignes.append(
            f"<tr{cls}><td><b>{JOURS[d.weekday()]} {d.strftime('%d/%m')}</b><br><small>{e(s['horaire'])}</small></td>"
            f"<td><b>{e(s['nom'])}</b> <small>({e(s['type'])})</small><br>"
            f"<a href=\"{e(s['lien'])}\">{e(s['sujet'])}</a><br>"
            f"<small>{e(s['discipline'])}{' · dir. ' + e(s['direction']) if s['direction'] else ''}</small></td>"
            f"<td>{e(labo)}</td><td>{e(s['lieu'])}{live}</td></tr>")
    n_info = sum(1 for s in liste if est_info(s))
    vide = '<tr><td colspan="4">Aucune soutenance à venir en informatique / LS2N.</td></tr>'
    corps = (vide + "\n" if n_info == 0 else "") + "\n".join(lignes)
    maj = dt.datetime.now().strftime("%d/%m/%Y à %H:%M")
    depot = os.environ.get("CI_PROJECT_URL", "")
    pied = f' · <a href="{e(depot)}">code source</a>' if depot else ""
    bascule = ""
    if avec_bascule:
        bascule = (f'<label><input type="checkbox" id="tout"> Afficher toutes les disciplines '
                   f'({len(liste)} soutenances, dont {n_info} en informatique / LS2N)</label>')
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(f"""<!doctype html><html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Soutenances à venir</title><style>
body{{font:15px/1.45 system-ui,sans-serif;margin:24px auto;max-width:1100px;padding:0 16px;color:#222;background:#fff}}
table{{border-collapse:collapse;width:100%;margin-top:12px}}td,th{{border-bottom:1px solid #ddd;padding:8px;text-align:left;vertical-align:top}}
th{{background:#f4f4f4}}a{{color:#0b5cad}}small{{color:#666}}label{{cursor:pointer}}
body:not(.tout) tr.autre{{display:none}}tr.autre td{{opacity:.75}}
@media (prefers-color-scheme:dark){{body{{background:#161616;color:#ddd}}th{{background:#262626}}td,th{{border-color:#333}}a{{color:#7ab7ff}}small{{color:#999}}}}
@media (max-width:640px){{table,tbody,tr,td{{display:block}}tr:first-child{{display:none}}td{{border:0;padding:2px 0}}tr{{border-bottom:1px solid #ddd;padding:8px 0}}}}
</style></head><body><h1>Soutenances à venir – informatique, Nantes</h1>
<p><small>Mis à jour le {maj} · sources : Nantes Université, agenda LS2N, Centrale Nantes{pied}</small></p>
{bascule}
<table><tr><th>Date</th><th>Candidat·e / sujet</th><th>Labo</th><th>Lieu</th></tr>
{corps}</table>
<script>var c=document.getElementById('tout');if(c)c.onchange=function(){{document.body.classList.toggle('tout',c.checked)}};</script>
</body></html>""")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tout", action="store_true", help="toutes disciplines, pas seulement l'informatique")
    ap.add_argument("--theses", action="store_true", help="thèses seulement (sans les HDR)")
    ap.add_argument("--depuis", type=int, default=0, metavar="N",
                    help="inclure aussi les soutenances des N derniers jours")
    ap.add_argument("--html", metavar="FICHIER", help="écrire aussi une page HTML")
    ap.add_argument("--json", action="store_true", help="sortie JSON")
    a = ap.parse_args()

    limite = dt.date.today() - dt.timedelta(days=a.depuis)
    sources = [_safe(nantes, limite) or [], _safe(ls2n, limite) or [],
               _safe(centrale, limite, a.tout) or []]
    toutes = [s for s in fusion(sources) if not (a.theses and s["type"] == "HDR")]
    liste = toutes if a.tout else [s for s in toutes if est_info(s)]

    if a.json:
        print(json.dumps(liste, ensure_ascii=False, indent=2))
    else:
        affiche(liste)
    if a.html:
        # la page contient toujours toutes les disciplines, l'informatique seule par défaut
        page_html(toutes, a.html, avec_bascule=True)
        print(f"Page HTML écrite : {a.html}", file=sys.stderr)


if __name__ == "__main__":
    main()
