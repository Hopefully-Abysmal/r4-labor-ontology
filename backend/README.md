## Backend (offline MVP)

### Setup

From `backend/`:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Run

```powershell
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/`.

### Data locations (local-only)

- SQLite: `../data/r4.sqlite`
- DuckDB: `../data/onet.duckdb`

Both are ignored by git.

