## Context

La change `database` fournit le schéma MariaDB du catalogue HP. Cette change construit le site web qui expose ce catalogue au public. La stack technique n'est pas encore choisie — cette spec se concentre sur les décisions fonctionnelles et architecturales.

## Goals / Non-Goals

**Goals:**
- Site web public en lecture seule pour consulter le catalogue HP
- Navigation par artistes, groupes, releases avec pages détail
- Recherche dans le catalogue
- Affichage des covers depuis des fichiers locaux

**Non-Goals:**
- Authentification et collection personnelle (change `my-collection`)
- Administration / saisie de données via le site
- API publique REST/GraphQL (pourra venir plus tard)
- Choix définitif de la stack technique (sera fait à l'implémentation)

## Decisions

### 1. Spec fonctionnelle, stack-agnostic

On décrit les pages et comportements attendus sans imposer de framework. La stack sera choisie au moment de l'implémentation — les candidats probables sont PHP (Laravel/Symfony), Node.js (Next.js/Nuxt), ou autre.

**Pourquoi :** Le projet est en phase de design. Fixer la stack trop tôt sans avoir implémenté le schéma DB serait prématuré.

### 2. Pages principales

```
/                          → Page d'accueil (dernières releases, stats)
/artists                   → Liste des artistes
/artists/:id               → Détail artiste (bio, groupes, releases)
/groups                    → Liste des groupes
/groups/:id                → Détail groupe (membres, discographie)
/releases                  → Liste des releases (filtrable par type)
/releases/:id              → Détail release (éditions, artistes/groupes)
/search?q=                 → Recherche globale
```

### 3. Covers servies depuis le filesystem

Les images de couverture sont stockées localement et identifiées par le `catalog_code` de la release (ex: `covers/EPCE-5645.jpg`). Le site sert ces fichiers statiquement. Si aucune cover n'existe pour un catalog_code, un placeholder est affiché.

### 4. Lecture seule

Le site ne permet aucune modification des données du catalogue. L'alimentation de la DB se fait par d'autres moyens (scripts d'import, admin directe).

## Risks / Trade-offs

- **Stack non choisie** → L'implémentation devra commencer par ce choix. Les specs sont suffisamment abstraites pour s'adapter à n'importe quel framework web.
- **Pas d'API** → Le site accède directement à la DB. Si une API devient nécessaire plus tard, il faudra refactorer. Acceptable pour un premier MVP.
- **Performance recherche** → La recherche full-text sur des noms japonais + romaji peut nécessiter un index FULLTEXT ou une solution externe (Meilisearch). À évaluer à l'implémentation.
