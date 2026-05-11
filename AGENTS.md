# AGENTS.md

## Contexte Projet

Ce dépôt contient un bot Discord Python permettant de jouer des fichiers audio
locaux dans des salons vocaux. Le bot est destiné à un usage JDR, sans service
cloud musical ni publicité.

## Contraintes Techniques

- Python 3.11+
- `discord.py` avec commandes slash uniquement
- Cogs de commandes sous forme de `GroupCog`
- SQLite pour le catalogue et les files d'attente persistées
- Configuration via `.env` avec `pydantic-settings`
- Ne jamais commiter `.env`, `.venv` ou le fichier SQLite local
- `ffmpeg` est requis pour la lecture audio

## Architecture

- `config`: chargement des variables d'environnement
- `models`: entités et gestion du schéma SQLite
- `services`: logique métier sans dépendance directe aux slash commands
- `cogs`: contrôleurs Discord slash commands
- `ui`: composants Discord interactifs, dont modals et views
- `utils`: fonctions transverses, notamment validation de fichiers audio

## SQLite

La base est initialisée au démarrage par `initialize_database`.

Cette fonction:

1. crée le dossier parent et le fichier SQLite si nécessaire;
2. crée les tables manquantes;
3. force `PRAGMA user_version = 1`;
4. vérifie que les tables exposent les colonnes requises.

Si le format attendu n'est pas trouvé, le bot doit échouer au démarrage plutôt
que migrer ou modifier des données de manière implicite.

## Règles de Contribution

- Garder la séparation UI, services, modèles et cogs.
- Documenter toute nouvelle classe et toute nouvelle fonction.
- Garder les commentaires ciblés sur la logique non évidente.
- Préférer des changements localisés et compatibles avec les patterns existants.
- Toute nouvelle constante opérationnelle doit être paramétrable via `.env` et
  documentée dans `.env.example`.
- Les autocomplete de musique doivent garder le nom exact de la musique comme
  valeur, tout en affichant les tags sous la forme `nom - tag1 | tag2`.
- Les listes longues exposées à Discord doivent utiliser une pagination avec
  boutons désactivés aux bornes plutôt que publier plusieurs messages.

## Vérification Recommandée

```bash
python -m compileall src
python -m discord_bot_zic
```

Le lancement réel nécessite un `.env` valide et un bot Discord invité sur un
serveur avec les permissions vocales adaptées.
