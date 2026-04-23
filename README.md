


[![GitHub Release][releases-shield]][releases]
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

[![Community Forum][forum-shield]][forum]


# Footao TV — Intégration HACS pour Home Assistant

Intégration personnalisée pour Home Assistant permettant de suivre les diffusions TV de vos équipes de football préférées via le site Footao.tv.

## ✨ Caractéristiques

📅 Suivi multi-équipes : Créez un capteur (sensor) par équipe.

📺 Infos complètes : Chaîne de diffusion, logos des clubs, date et heure précises.

⚙️ Configuration simple : Tout se passe via l'interface utilisateur de Home Assistant.

🔔 Prêt pour les automatisations : Idéal pour créer des notifications avant les matchs.


## 🔧 Attributs disponibles par sensor

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

## 🏗️ Installation via HACS

1. Dans HACS → **Intégrations** → menu ⋮ → **Dépôts personnalisés**
2. Ajouter l'URL de ce dépôt GitHub, catégorie **Integration**
   https://github.com/developpeurbox/hass-footao.git
4. Installer **Footao TV**
5. Redémarrer Home Assistant
6. **Paramètres → Appareils & services → Ajouter une intégration → Footao TV**

## 🏗️ Installation manuelle

1. Téléchargez le dossier `custom_components/footao/` de ce dépôt.
2. Copiez-le dans le dossier `custom_components/footao/`  de votre instance Home Assistant.
3. Redémarrez Home Assistant


## 🌟 Configuration

Les équipes se saisissent depuis l'UI au moment de l'ajout de l'intégration :

```
Marseille Saint-Etienne PSG
```
![Footao ligues](/doc/images/ligues.png "Footao ligue").
![Footao clubs](/doc/images/clubs.png "Footao clubs").

Tu peux les modifier ensuite via **Configurer** sur la carte de l'intégration.

![Footao resultat](/doc/images/resultat.png "Footao resultat").

## 🔁 Rafraîchissement

Les données sont mises à jour automatiquement **toutes les 24 heures**. Tu peux forcer un rafraîchissement depuis l'UI de l'intégration.

## 🎨 Affichage & Notifications

### Carte dédiée

Pour un rendu visuel optimal, utilisez la carte compagnon :
👉 [**Footao Game Card**](https://github.com/developpeurbox/footao-game-card)


### Notification 

Voici une automatisation pour recevoir un rappel sur votre téléphone le matin du match à 08:00 :

```yaml
alias: Notification Match Angers Aujourd'hui
description: >-
  Envoie une notification si le match d'Angers a lieu aujourd'hui (comparaison
  date uniquement)
triggers:
  - at: "08:00:00"
    trigger: time
conditions:
  - condition: template
    value_template: >
      {{ state_attr('sensor.footao_angers', 'datetime').split(' ')[0] ==
      now().strftime('%Y-%m-%d') }}
actions:
  - data:
      title: "⚽ Jour de match !"
      message: >
        Le match {{ state_attr('sensor.footao_angers', 'event_name') }} est
        diffusé aujourd'hui à {{ state_attr('sensor.footao_angers',
        'datetime').split(' ')[1] }} sur {{ state_attr('sensor.footao_angers',
        'chaine') }}.
    action: notify.mobile_xxxx
mode: single
```

[commits-shield]: https://img.shields.io/github/commit-activity/y/custom-components/readme.svg?style=for-the-badge
[commits]: https://github.com/developpeurbox/hass-footao/readme/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge
[exampleimg]: example.png
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[releases-shield]: https://img.shields.io/github/v/release/developpeurbox/hass-footao?style=for-the-badge
[releases]: https://github.com/developpeurbox/hass-footao/releases

