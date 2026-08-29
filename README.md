[![GitHub Release][releases-shield]][releases]
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

[![Community Forum][forum-shield]][forum]


# Footao TV — Intégration HACS pour Home Assistant

Intégration personnalisée pour Home Assistant permettant de suivre les diffusions TV de vos équipes de football préférées via le site Footao.tv, avec sa carte Lovelace dédiée **incluse**.

![Exemple Footao Game Card](/doc/images/example.png "Exemple d'affichage")

## ✨ Caractéristiques

📅 Suivi multi-équipes : Créez un capteur (sensor) par équipe.

📺 Infos complètes : Chaîne de diffusion, logos des clubs, date et heure précises.

⚙️ Configuration simple : Tout se passe via l'interface utilisateur de Home Assistant.

🎴 Carte Lovelace intégrée : Aucune installation séparée, la carte est prête à l'emploi dès l'installation de l'intégration.

🔔 Prêt pour les automatisations : Idéal pour créer des notifications avant les matchs.


<details>
<summary><h2>🔧 Attributs disponibles par sensor</h2></summary>

| Attribut | Description |
|---|---|
| `state` | Nom de la chaîne TV (ex: TF1) |
| `team` | Nom de l'équipe suivie |
| `logoTeam` | URL du logo de l'équipe suivie |
| `domicile` | Équipe à domicile |
| `logoDomicile` | URL du logo de l'équipe à domicile |
| `exterieur` | Équipe à l'extérieur |
| `logoExterieur` | URL du logo de l'équipe à l'extérieur |
| `situation` | `dom` ou `ext` selon le rôle de l'équipe suivie |
| `competition` | Nom de la compétition (ex: Ligue 1, Amical) |
| `date` | Date du match (ex: jeudi 4 juin) |
| `datetime` | Date/heure ISO (ex: 2026-06-04 21:10:00) |
| `datetime_fin` | Fin estimée ISO (ex: 2026-06-05 00:10:00) |
| `display` | `true` si le match est dans le futur |
| `heure` | Heure de diffusion (ex: 21:10) |
| `chaine` | Nom de la chaîne TV |
| `logo` | Style CSS du sprite chaîne (footao.tv) |
| `game` | Texte brut du match (ex: France · Côte d'Ivoire) |
| `clubs_updated_at` | Date de dernière mise à jour du fichier clubs |
| `clubs_source` | Source du fichier clubs (ex: `github`) |

</details>

## 🏗️ Installation via HACS

1. Dans HACS → **Intégrations** → menu ⋮ → **Dépôts personnalisés**
2. Ajouter l'URL de ce dépôt GitHub, catégorie **Integration**
   https://github.com/developpeurbox/hass-footao.git
4. Installer **Footao TV**
5. Redémarrer Home Assistant
6. **Paramètres → Appareils & services → Ajouter une intégration → Footao TV**

> 🎴 La carte Lovelace `footao-game-card` est automatiquement enregistrée par l'intégration au démarrage — pas besoin d'installer un dépôt séparé ni d'ajouter une ressource manuellement.

## 🏗️ Installation manuelle

1. Téléchargez le dossier `custom_components/footao/` de ce dépôt.
2. Copiez-le dans le dossier `custom_components/footao/` de votre instance Home Assistant.
3. Redémarrez Home Assistant

## 🌟 Configuration

Les équipes se saisissent depuis l'UI au moment de l'ajout de l'intégration :

![Footao ligues](/doc/images/ligues.png "Footao ligue").
![Footao clubs](/doc/images/clubs.png "Footao clubs").

Tu peux les modifier ensuite via **Configurer** sur la carte de l'intégration.

![Footao resultat](/doc/images/resultat.png "Footao resultat").

## 🔁 Rafraîchissement

Les données sont mises à jour automatiquement **toutes les 6 heures**. Tu peux forcer un rafraîchissement depuis l'UI de l'intégration.

---

## 🏟️ Fichier des clubs — `clubs.json`

L'intégration s'appuie sur un fichier `clubs.json` pour associer chaque nom de club (tel qu'il apparaît sur footao.tv) à un logo provenant de [TheSportsDB](https://www.thesportsdb.com/).

### 📄 Structure du fichier

```json
{
  "Paris Saint-Germain": "https://www.thesportsdb.com/images/media/team/badge/xwqputsd.png",
  "Olympique de Marseille": "https://www.thesportsdb.com/images/media/team/badge/yv2d7s1473502891.png",
  "AS Saint-Étienne": "https://www.thesportsdb.com/images/media/team/badge/abc123.png"
}
```

Chaque entrée est une paire **clé → valeur** :
- **Clé** : le nom exact du club tel qu'il apparaît dans les données de footao.tv (sensible à la casse et aux accents).
- **Valeur** : l'URL du logo du club, de préférence issu de TheSportsDB.

### 🤝 Contribuer — Ajouter ou corriger un club

Le fichier `clubs.json` est **ouvert aux contributions**. Si un club n'est pas reconnu ou si son logo est manquant/incorrect, tout le monde peut proposer une mise à jour.

**Étapes pour contribuer :**

1. **Forker** ce dépôt GitHub.
2. Ouvrir le fichier [`custom_components/footao/clubs.json`](custom_components/footao/clubs.json).
3. Ajouter ou corriger l'entrée du club concerné :
   - Trouver le **nom exact** du club sur [footao.tv](https://footao.tv) (ex: depuis le texte d'un match affiché).
   - Trouver l'**URL du logo** correspondant sur [TheSportsDB](https://www.thesportsdb.com/).
     > 💡 Chercher le club sur `https://www.thesportsdb.com/`, ouvrir sa fiche et copier l'URL du badge.
4. Soumettre une **Pull Request** avec une description claire (club ajouté, ligue, pays).

**Exemple de PR :**

```
Ajout : Brest (Stade Brestois 29) — Ligue 1
```

> ⚠️ Le nom de la clé doit correspondre **exactement** à ce que retourne footao.tv, sinon le logo ne sera pas affiché.

### 🔍 Comment trouver le bon nom de club ?

Si tu n'es pas sûr du nom exact utilisé par footao.tv, tu peux le retrouver dans les **attributs du sensor** Home Assistant :
- L'attribut `domicile` ou `exterieur` contient le nom brut tel que scrapé depuis footao.tv.
- C'est cette valeur qui doit être utilisée comme clé dans `clubs.json`.

---

## 🎨 Footao Game Card

La carte Lovelace `footao-game-card` est fournie avec l'intégration : elle apparaît directement dans le sélecteur **Ajouter une carte** de l'éditeur de tableau de bord une fois l'intégration installée.

### 🎯 Utilisation

Ajoutez simplement ce code dans votre configuration :

```yaml
type: custom:footao-game-card
entity: sensor.footao_lorient  # Remplacez par votre entité de capteur
footer_bg: "rgba(0,0,0,0.6)"   # Couleur d'arrière-plan du pied de page
footer_color: "#ffffff"        # Couleur du texte du pied de page
```

Pour avoir tous vos matchs :

```yaml
type: custom:auto-entities
card:
  type: entities
  colum: 2
  square: false
filter:
  include:
    - options:
        type: custom:footao-game-card
      entity_id: sensor.footao*
      sort:
        method: attribute
        attribute: date
grid_options:
  columns: 12
  rows: auto
```

![Exemple Footao Game Card](/doc/images/all.png "Tous les matchs")

### 🎨 Personnalisation

Vous pouvez personnaliser l'apparence du pied de page (*footer*) directement via les options de la carte :

* **Arrière-plan :** Modifiez `footer_bg` (accepte les formats **HEX**, **RGB** ou **RGBA**).
* **Couleur du texte :** Ajustez `footer_color` pour assurer une visibilité optimale selon votre fond.

### 📭 Aucun match prévu

Lorsque aucun match n'est trouvé pour l'équipe configurée (match passé ou calendrier vide), la carte affiche automatiquement un état simplifié : le logo de l'équipe, son nom, et un message d'information.

![Carte aucun match](/doc/images/example_no_game.png "Affichage sans match prévu")

> **Aucun match prévu prochainement** s'affiche à la place des informations de diffusion habituelles. Dès qu'un prochain match est disponible dans le capteur, la carte reprend son affichage normal automatiquement.

---

## 🔔 Notifications

Voir les [**Footao blueprints**](https://github.com/developpeurbox/hass-footao/blob/main/blueprints/readme.md) pour recevoir un rappel sur votre téléphone le matin du match à 08:00.

---

## 💬 Communauté & Support

🗣️ **Forum Home Assistant** : [Discuter ici](https://community.home-assistant.io/)

---

[commits-shield]: https://img.shields.io/github/commit-activity/y/custom-components/readme.svg?style=for-the-badge
[commits]: https://github.com/developpeurbox/hass-footao/readme/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge
[exampleimg]: example.png
[forum-shield]: https://img.shields.io/badge/community-forum-brightgreen.svg?style=for-the-badge
[forum]: https://community.home-assistant.io/
[releases-shield]: https://img.shields.io/github/v/release/developpeurbox/hass-footao?style=for-the-badge
[releases]: https://github.com/developpeurbox/hass-footao/releases
