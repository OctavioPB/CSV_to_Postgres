# CSV to PostgreSQL — ETL Pipeline

A Flask-based ETL platform for uploading CSV files, exploring and validating data interactively, and scheduling recurring import jobs into PostgreSQL.

---

## Features

- **Upload** — drag-and-drop CSV upload with configurable target table name
- **Explore** — automatic type inference (int, float, datetime, bool, str) with per-column override dropdowns before committing to the database
- **Jobs** — schedule recurring ETL jobs via cron or interval expressions; trigger manually from the UI
- **Bulk insert** — chunked SQLAlchemy Core inserts (1 000 rows/batch) with per-batch transaction rollback on error
- **OPB brand UI** — navy + gold design system with Fraunces + Plus Jakarta Sans typography

---

## Tech Stack

| Layer | Tool |
|---|---|
| Web framework | Flask 3 |
| Database | PostgreSQL 16 (Docker) |
| ORM / inserts | SQLAlchemy Core + psycopg2-binary |
| Migrations | Flask-Migrate (Alembic) |
| Data profiling | Pandas 2 |
| Scheduling | APScheduler 3 (BackgroundScheduler) |
| Config | python-dotenv |

---

## Quick Start

### 1. Clone and configure

```bash
git clone <repo-url>
cd CSV_to_Postgres
cp .env.example .env
# Edit .env with your credentials if needed
```

### 2. Start PostgreSQL

```bash
docker compose up -d
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Initialize the database

```bash
flask db init
flask db migrate -m "initial schema"
flask db upgrade
```

### 5. Run the dev server

```bash
flask run
```

Open [http://localhost:5000](http://localhost:5000).

---

## Environment Variables

Copy `.env.example` to `.env`. Never commit `.env`.

| Variable | Default | Description |
|---|---|---|
| `FLASK_ENV` | `development` | Flask environment |
| `SECRET_KEY` | `change_me` | Session signing key |
| `POSTGRES_HOST` | `localhost` | Database host |
| `POSTGRES_PORT` | `5432` | Database port |
| `POSTGRES_DB` | `etl_db` | Database name |
| `POSTGRES_USER` | `etl_user` | Database user |
| `POSTGRES_PASSWORD` | `etl_pass` | Database password |
| `UPLOAD_FOLDER` | `uploads` | Temp storage for uploaded CSVs |
| `MAX_CONTENT_LENGTH` | `16777216` | Max upload size in bytes (16 MB) |

---

## Usage

### Upload tab

1. Select a `.csv` file (max 16 MB)
2. Enter a target table name (snake_case recommended)
3. Click **Upload & Explore**

### Explore tab

- Inspect the inferred column types, null percentages, and sample values
- Override types via the dropdown in each row
- Columns flagged **⚠ high null** exceed 95% missing values
- Click **Confirm & Insert** to write to PostgreSQL

### Jobs tab

Schedule recurring ETL jobs for files available on the server filesystem.

**Cron format** — standard 5-part cron expression:
```
0 6 * * *       # daily at 06:00
30 8 * * 1-5    # weekdays at 08:30
```

**Interval format** — prefix `interval:` with key=value pairs:
```
interval:minutes=30
interval:hours=1
interval:hours=2,minutes=30
```

Each job requires:
- **Process name** — display label
- **Schedule** — cron or interval string
- **Source CSV path** — absolute path on the server filesystem
- **Target table** — PostgreSQL table name (created if it does not exist)

---

## Project Structure

```
CSV_to_Postgres/
├── run.py                      # Flask entry point
├── docker-compose.yml
├── requirements.txt
├── .env.example
│
├── app/
│   ├── __init__.py             # create_app() factory
│   ├── config.py               # Config, TestingConfig
│   ├── extensions.py           # db, migrate, scheduler singletons
│   │
│   ├── models/
│   │   ├── job.py              # ETLJob model
│   │   └── upload_log.py       # UploadLog model
│   │
│   ├── routes/
│   │   ├── upload.py           # GET/POST /upload
│   │   ├── explore.py          # GET /explore, POST /explore/confirm
│   │   └── jobs.py             # GET/POST /jobs, /jobs/<id>/trigger
│   │
│   ├── services/
│   │   ├── csv_processor.py    # parse_csv(), profile_csv(), type inference
│   │   ├── db_manager.py       # sanitize, create table, bulk_insert
│   │   └── scheduler.py        # APScheduler init, register, trigger
│   │
│   ├── templates/
│   │   ├── base.html
│   │   ├── upload.html
│   │   ├── explore.html
│   │   └── jobs.html
│   │
│   └── static/
│       ├── css/main.css
│       └── js/main.js
│
├── uploads/                    # Temp CSV storage (gitignored)
├── migrations/                 # Flask-Migrate output
└── tests/
    ├── test_csv_processor.py
    ├── test_db_manager.py
    └── test_scheduler.py
```

---

## Running Tests

Tests for `csv_processor`, `db_manager`, and `scheduler` run without a database connection:

```bash
pytest tests/ -v
```

Integration tests against a live Postgres connection use the `TEST_POSTGRES_DB` environment variable (defaults to `etl_test_db`):

```bash
TEST_POSTGRES_DB=etl_test_db pytest tests/ -v
```

---

## Data Flow

```
CSV Upload
  └─► csv_processor.parse_csv()        # dtype=str, strip whitespace
        └─► csv_processor.profile_csv() # shape, nulls, inferred types, samples
              └─► session stores UUID → temp file

Explore (user reviews & overrides types)
  └─► POST /explore/confirm
        └─► db_manager.build_column_map()           # sanitize names, resolve types
              └─► db_manager.create_table_if_not_exists()
                    └─► db_manager.coerce_dataframe()
                          └─► db_manager.bulk_insert()  # 1 000 rows/batch, per-batch txn
                                └─► UploadLog written to DB

Scheduled Job
  └─► APScheduler fires _run_job_fn()
        └─► same pipeline as above, triggered automatically
              └─► ETLJob.status updated → UploadLog written
```

---

## Type Inference Priority

For each column the processor tries types in this order, stopping at the first match:

1. `int64` — all non-null values parse as integers
2. `float64` — all non-null values parse as floats
3. `datetime` — matched against 7 date/time formats (ISO 8601 first)
4. `bool` — values are a subset of `{true, false, yes, no, 1, 0, t, f, y, n}`
5. `str` — fallback

---

## Column Name Sanitization

Column names are transformed before table creation:

- Lowercased
- Spaces and non-alphanumeric characters replaced with `_`
- Consecutive underscores collapsed
- Leading digits prefixed with `col_`
- PostgreSQL reserved keywords suffixed with `_col`

---

## License

MIT
