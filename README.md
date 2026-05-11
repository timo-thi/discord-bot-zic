# discord-bot-zic

Bot Discord pour jouer des musiques locales depuis la machine qui héberge le bot.

Le bot utilise uniquement des commandes slash Discord. Il garde un catalogue SQLite
des fichiers connus et une file d'attente persistée par serveur Discord.

## Prérequis

- Python 3.11 ou plus récent
- `ffmpeg` installé et disponible dans le `PATH`
- Un bot Discord avec les permissions nécessaires:
  - utiliser les commandes d'application
  - rejoindre un salon vocal
  - parler dans un salon vocal
  - envoyer des messages dans le salon de logs

## Installation

Crée un environnement virtuel local:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Le dossier `.venv` est ignoré par Git.

## Configuration

Copie le fichier d'exemple:

```bash
cp .env.example .env
```

Puis remplis les variables:

```dotenv
DISCORD_TOKEN=token_du_bot
DISCORD_GUILD_ID=123456789012345678
DISCORD_LOG_CHANNEL_ID=123456789012345678
SQLITE_PATH=./data/discord-bot-zic.sqlite3
MUSIC_ROOT=./music
IDLE_TIMEOUT_SECONDS=600
FFMPEG_EXECUTABLE=ffmpeg
DEFAULT_VOLUME_PERCENT=100
AUTOCOMPLETE_LIMIT=25
STORE_LIST_PAGE_SIZE=10
```

`DISCORD_GUILD_ID` est optionnel. S'il est renseigné, les commandes slash sont
synchronisées uniquement sur ce serveur, ce qui est plus rapide en développement.
S'il est absent ou vide, les commandes sont synchronisées globalement.

`MUSIC_ROOT` est optionnel. Quand il est renseigné, les chemins relatifs saisis
dans les modals sont résolus depuis ce dossier. Les chemins absolus restent
acceptés.

## Lancement

```bash
source .venv/bin/activate
python -m discord_bot_zic
```

Au démarrage, le bot crée le fichier SQLite s'il n'existe pas, crée les tables
manquantes et vérifie le format attendu de la base. Si la version ou les colonnes
attendues ne correspondent pas, le démarrage échoue pour éviter de corrompre les
données.

## Commandes

### `/music`

- `/music connect resume_queue:false`
  Connecte le bot au salon vocal de l'utilisateur. Si `resume_queue` vaut `true`,
  restaure la file d'attente sauvegardée pour ce serveur.
- `/music play filter:<optionnel> shortcut_queue:false`
  Filtre le catalogue sur le nom et les tags. Si une seule musique correspond,
  elle est jouée immédiatement ou ajoutée à la file si une lecture est déjà en
  cours. Sans paramètre, reprend la lecture en pause ou joue la prochaine musique
  de la file. L'autocomplete affiche les choix sous la forme
  `nom musique - tag1 | tag2`. Si `shortcut_queue` vaut `true`, la musique est
  placée au début de la file au lieu de la fin.
- `/music pause`
  Met la musique en pause.
- `/music skip`
  Passe à la musique suivante. Si la file est vide, met la lecture en pause.
- `/music stop`
  Arrête la lecture, sauvegarde la file d'attente restante et quitte le vocal.
- `/music volume value:<0-100>`
  Ajuste le volume de lecture du bot pour le serveur courant. La valeur initiale
  vient de `DEFAULT_VOLUME_PERCENT`.
- `/music queue`
  Affiche la musique en cours, la file d'attente et une vue de contrôle simple
  avec boutons Play/Pause, Skip et Stop. Le bouton Play/Pause change selon
  l'état de lecture.

### `/store`

- `/store add`
  Ouvre un modal pour saisir le chemin du fichier, le nom optionnel et les tags.
  Le fichier est validé avant insertion: il doit exister, être un fichier, et
  avoir une extension audio supportée.
- `/store list`
  Liste les musiques connues dans un embed. Si le catalogue dépasse
  `STORE_LIST_PAGE_SIZE`, des boutons Précédent/Suivant permettent de paginer.
  Les boutons sont désactivés automatiquement en début et fin de pagination.
- `/store remove music_name:<nom>`
  Retire une musique du catalogue. Les entrées de queue liées sont supprimées
  par SQLite. L'autocomplete affiche aussi les tags.
- `/store edit music_name:<nom>`
  Ouvre un modal prérempli pour modifier le chemin, le nom et les tags.
  L'autocomplete affiche aussi les tags.

Les tags sont séparés par des espaces et ne peuvent pas contenir d'espace.

## Formats audio supportés

Le catalogue accepte les extensions suivantes:

`.aac`, `.flac`, `.m4a`, `.mp3`, `.ogg`, `.opus`, `.wav`, `.webm`

La lecture réelle dépend aussi de ce que ton installation de `ffmpeg` sait lire.

## Structure

- `src/discord_bot_zic/config`: configuration `.env` avec `pydantic-settings`
- `src/discord_bot_zic/models`: entités et initialisation SQLite
- `src/discord_bot_zic/services`: logique métier catalogue, queue, logs, lecture
- `src/discord_bot_zic/cogs`: contrôleurs slash commands avec `GroupCog`
- `src/discord_bot_zic/ui`: modals et views Discord
- `src/discord_bot_zic/utils`: validation des fichiers audio
