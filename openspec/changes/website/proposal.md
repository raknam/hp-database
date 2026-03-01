## Why

La base de données HP n'a de valeur que si elle est accessible. Il faut un site web pour exposer le catalogue complet (artistes, groupes, discographie) en consultation publique. Ce site servira aussi de socle pour les fonctionnalités authentifiées (collection personnelle) dans la change `my-collection`.

## What Changes

- Mise en place d'un site web exposant le catalogue HP en lecture seule
- Pages de navigation : liste/détail pour les artistes, groupes, releases
- Recherche dans le catalogue
- Affichage des covers (images locales identifiées par catalog_code)
- Stack technique à définir (spec fonctionnelle uniquement pour l'instant)

## Capabilities

### New Capabilities
- `catalog-browsing`: Navigation publique dans le catalogue — listes, pages détail artistes/groupes/releases, recherche
- `cover-display`: Affichage des images de couverture des releases à partir des fichiers locaux

### Modified Capabilities

_(aucune)_

## Impact

- Dépendance sur la change `database` (le schéma doit exister)
- Nouveau code applicatif (framework à choisir)
- Serveur de fichiers statiques pour les covers
