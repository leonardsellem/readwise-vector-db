# Readwise Vector DB

This project provides a complete ETL (Extract, Transform, Load) pipeline to sync your Readwise highlights, embed them using OpenAI, and store them in a PostgreSQL database with `pgvector` for similarity searches.

It includes a backfill command to fetch all your historical highlights and an incremental sync command, designed to be run on a schedule (e.g., via GitHub Actions), to keep your database up-to-date with the latest highlights.

## Features

- **Full Backfill**: Sync all your historical Readwise highlights.
- **Incremental Sync**: Only fetch highlights created or updated since the last sync.
- **OpenAI Embeddings**: Automatically generate embeddings for your highlights.
- **PostgreSQL + pgvector**: Store highlights and vectors efficiently.
- **Alembic Migrations**: Manage database schema changes.
- **GitHub Actions**: Automated nightly syncs.

## Setup and Usage

### 1. Prerequisites

- [Poetry](https://python-poetry.org/) for dependency management.
- [Docker](https://www.docker.com/) and Docker Compose for running the database.

### 2. Installation

Clone the repository and install the dependencies:

```bash
git clone <repository_url>
cd readwise-vector-db
poetry install
```

### 3. Environment Variables

Create a `.env` file in the root of the project and add the following variables:

```env
# Your Readwise access token
READWISE_TOKEN=your_readwise_token

# Your OpenAI API key
OPENAI_API_KEY=your_openai_api_key

# Optional: Customize your database connection
# POSTGRES_USER=postgres
# POSTGRES_PASSWORD=postgres
# POSTGRES_DB=readwise
# DATABASE_URL=postgresql+psycopg://user:password@host:port/dbname
```

The `DATABASE_URL` is constructed from the other `POSTGRES_*` variables if not provided directly.

### 4. Running the Database

Start the PostgreSQL database using Docker Compose:

```bash
docker compose up -d db
```

### 5. Database Migrations

Apply the latest database migrations:

```bash
poetry run alembic upgrade head
```

### 6. Running a Full Backfill

To perform an initial sync of all your Readwise highlights, run the backfill command:

```bash
poetry run rwv sync --backfill
```

This will fetch all highlights, embed them, and store them in the database.

### 7. Running an Incremental Sync

After a successful backfill, you can run incremental syncs to fetch only new or updated highlights.

The command will automatically use the timestamp from the last successful sync:
```bash
poetry run rwv sync
```

You can also specify a date manually:
```bash
poetry run rwv sync --since YYYY-MM-DD
```

### 8. Validation

You can validate that the data has been synced correctly by connecting to the database and querying the `highlight` and `syncstate` tables.

### 9. Automated Sync with GitHub Actions

This repository includes a GitHub Actions workflow (`.github/workflows/sync.yml`) that runs the incremental sync nightly. To enable it, you need to add the following secrets to your GitHub repository settings:

- `READWISE_TOKEN`
- `OPENAI_API_KEY`
- `DATABASE_URL` (if your database is publicly accessible)

The workflow will run at 03:00 UTC every day.
