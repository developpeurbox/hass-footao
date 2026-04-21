# Footao TV — Intégration HACS pour Home Assistant

Crée des entités `sensor` dans Home Assistant avec les prochains matchs de foot diffusés sur [Footao.tv](https://www.footao.tv), pour les équipes de ton choix.

## Attributs disponibles par sensor

| Attribut | Description |
|---|---|
| `team` | Nom de l'équipe suivie |
| `team logo` | Logo de l'équipe suivie |
| `domicile` | Équipe à domicile |
| `logoDomicile` | URL du logo de l'équipe à domicile |
| `exterieur` | Équipe à l'extérieur |
| `logoExterieur` | URL du logo de l'équipe à l'extérieur |
| `opponent` | Adversaire |
| `situation` | `dom` ou `ext` |
| `date` | Date du match (ex: Samedi 19 Avril 2026) |
| `datetime` | Date/heure ISO (ex: 2026-04-19 20:45:00) |
| `display` | `true` si le match est dans le futur |
| `heure` | Heure de diffusion (ex: 20:45) |
| `chaine` | Nom de la chaîne TV |
| `logo` | Style CSS du sprite chaîne (footao.tv) |
| `game` | Texte brut du match (ex: Marseille · Lyon) |

## Installation via HACS

1. Dans HACS → **Intégrations** → menu ⋮ → **Dépôts personnalisés**
2. Ajouter l'URL de ce dépôt GitHub, catégorie **Integration**
3. Installer **Footao TV**
4. Redémarrer Home Assistant
5. **Paramètres → Appareils & services → Ajouter une intégration → Footao TV**

## Installation manuelle

Copier le dossier `custom_components/footao/` dans ton dossier `config/custom_components/`.

## Configuration

Les équipes se saisissent depuis l'UI au moment de l'ajout de l'intégration, séparées par des virgules :

```
Marseille, Saint-Etienne, PSG
```

Tu peux les modifier ensuite via **Configurer** sur la carte de l'intégration.

## Rafraîchissement

Les données sont mises à jour automatiquement **toutes les 6 heures**. Tu peux forcer un rafraîchissement depuis l'UI de l'intégration.
