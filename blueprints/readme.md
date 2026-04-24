# Quelques blueprint pour Home Assistant

## ⚽ Notification jour de match – Football (multi-clubs)
[![Open your Home Assistant instance and show the blueprint import dialog with a specific blueprint pre-filled.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fdeveloppeurbox%2Fhass-footao%2Fblob%2Fmain%2Fblueprints%2Fnotification-game-day.yaml)


### 📌 Description

Ce blueprint Home Assistant permet d’envoyer automatiquement une **notification lorsqu’un ou plusieurs matchs de football ont lieu aujourd’hui**.

La détection se base sur un **attribut texte `date`** présent sur les capteurs (`"Aujourd'hui"`), sans calcul ni conversion de date système.

Fonctionnalités clés :
- ✅ Gestion de **plusieurs clubs / capteurs**
- ✅ **Une seule notification** récapitulative
- ✅ **Titre personnalisable**
- ✅ **Message personnalisable** via templates Jinja
- ✅ Compatible UI Home Assistant (selectors)

---

## ⚙️ Fonctionnement

1. Le blueprint s’exécute une fois par jour à l’heure configurée
2. Il parcourt tous les capteurs sélectionnés
3. Il conserve ceux dont :
   ```jinja
   state_attr(sensor, 'date') == "Aujourd'hui"


---
