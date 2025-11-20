# Prépas MP2I/MPI

Ce bot discord a pour but d'ajouter des fonctionnalités au serveur discord [Prépas MP2I/MPI](https://discord.prepas-mp2i.org).

## Installation

Ce projet utilise [uv](https://github.com/astral-sh/uv) comme gestionnaire de paquets Python et [pypy](https://github.com/pypy/pypy) pour l'implémentation de Python 3.11. Le bot discord utilise une base de données [PostgreSQL](https://github.com/postgres/postgres) afin de sauvegarder des données nécessaires à son fonctionnement.

### Natif

Une fois le dépôt cloné et les dépendances installées, synchronisez les dépendances du projet avec la commande

```sh
uv sync
```

Créez les fichiers de configuration et d'environnement de variables à partir des fichiers d'exemples puis modifiez-les pour votre utilisation

```sh
cp .env{.example,}; cp config.toml{.example,}
vim .env config.toml # ou autre éditeur de texte préféré
```

Vous pouvez dès lors démarrer le bot discord via la commande

```sh
uv run -m mp2i
```

### Docker

Le bot discord peut également être démarré dans un container. La base de données est alors directement intégrée dans un autre container relié à celui du bot discord. Vous pouvez les démarrer avec la commande

> Votre installation de Docker peut requérir un accès administrateur à la machine, vous devez alors soit être dans le groupe `docker` soit rajouter `sudo` devant la commande. Cette note est valable pour toutes les commandes Docker.

```sh
docker compose up
```

L'ajout de l'option `-d` permet de détacher l'exécution du terminal. Auquel cas, il est possible d'arrêter les containers avec la commande

```sh
docker compose down
```

Pour démarrer le bot discord avec de nouveaux changements effectués, il est nécessaire de recréer l'image Docker. Pour ce faire, il faut rajouter l'option `--build` lors du démarrage des containers. La commande suivante recrée l'image Docker et détache l'exécution des containers du terminal.

```sh
docker compose up --build -d
```
