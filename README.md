# Soutenances à venir – informatique, Nantes

Petit script Python qui liste **en direct** les soutenances de thèse (et HDR) à venir
en informatique à Nantes, en interrogeant à chaque lancement :

1. **Nantes Université** – page [Soutenances de thèses](https://www.univ-nantes.fr/recherche-et-innovation/doctorat/soutenances-de-theses)
   (section « à venir ») ; chaque fiche est lue pour récupérer discipline, direction,
   laboratoire, heure et salle.
2. **Agenda du LS2N** – via l'API WordPress publique de [ls2n.fr](https://www.ls2n.fr)
   (thèses et HDR du labo, tous établissements : Nantes Université, Centrale, IMT Atlantique).
3. **Centrale Nantes** – page [PhD Defenses](https://research.ec-nantes.fr/en/phd-defenses)
   (ED MaSTIC ou laboratoire LS2N).

Les doublons entre sources sont fusionnés.

## Utilisation

Aucune dépendance : Python 3.8+ suffit.

```bash
python3 soutenances.py                    # à venir, informatique / LS2N
python3 soutenances.py --tout             # à venir, toutes disciplines
python3 soutenances.py --theses           # sans les HDR
python3 soutenances.py --depuis 15        # inclut aussi les 15 derniers jours
python3 soutenances.py --html page.html   # écrit aussi une page HTML
python3 soutenances.py --json             # sortie JSON
```

Exemple de sortie :

```
ven. 13/11/2026  à 14 heures  [Thèse]  Josselin POIRET
   « Nouveaux types pour la théorie des types de Martin-Löf »
   Informatique | dir. Nicolas TABAREAU | LS2N
   Faculté des Sciences et des Techniques, Amphithéâtre LS2N (RDC) - Bâtiment 34, ...
   https://www.univ-nantes.fr/recherche-et-innovation/doctorat/josselin-poiret-...  (Nantes Université)
```

## Page web mise à jour automatiquement

La page générée affiche l'informatique / LS2N par défaut, avec une case à cocher pour
afficher toutes les disciplines ; les données sont aussi publiées en JSON (`soutenances.json`).

### GitHub Pages

Le workflow `.github/workflows/pages.yml` régénère et publie la page à chaque push sur
`main`, tous les jours à 5h UTC, et à la demande (*Actions → Page des soutenances →
Run workflow*). Pages doit être réglé sur *Source : GitHub Actions*
(*Settings → Pages*).

GitHub suspend les workflows programmés d'un dépôt public après 60 jours sans activité :
il suffit alors de le réactiver depuis l'onglet *Actions*.

### GitLab Pages (gitlab.univ-nantes.fr)

Le fichier `.gitlab-ci.yml` fait la même chose avec GitLab Pages, à chaque push sur `main`.
Pour la mise à jour quotidienne, créer un pipeline programmé :
*Build → Pipeline schedules → New schedule*, par exemple `0 6 * * *`, fuseau `Europe/Paris`,
branche `main`. La visibilité de la page se règle dans
*Settings → General → Visibility → Pages*.

## Filtre « informatique »

Une soutenance est retenue si sa discipline contient « informatique », **ou** si son
laboratoire est le LS2N, **ou** si elle relève de l'ED MaSTIC à Centrale. Le LS2N couvrant
aussi l'automatique et la robotique, la discipline est affichée pour permettre le tri.
`--tout` désactive le filtre.

## Limites

- Le script ne voit que ce qui est publié sur ces trois sites : une soutenance annoncée
  seulement par mail, ou à l'IMT Atlantique hors agenda LS2N, n'apparaît pas.
- Il lit le HTML des pages : si un site change de mise en page, l'extraction peut casser
  (une source en erreur est signalée sur stderr sans bloquer les autres).
- theses.fr n'est pas utilisé : les thèses en cours n'y ont pas de date de soutenance.
