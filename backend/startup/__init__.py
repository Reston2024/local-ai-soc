"""
backend.startup — Application startup modules.

Decomposed from backend/main.py for clarity:
  stores.py     — store initialisation (DuckDB, Chroma, SQLite, services)
  workers.py    — background async task workers (feed sync, triage, anomaly, etc.)
  collectors.py — data-collection tasks (osquery, firewall, Malcolm, WinEvent)
  routers.py    — router mounting (all app.include_router calls)
"""
