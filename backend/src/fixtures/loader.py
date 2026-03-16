"""Load fixture events from NDJSON file into in-memory store."""
import json
from pathlib import Path

def load_ndjson(path: str | Path, store: list, normalizer, rule_engine) -> dict:
    path = Path(path)
    if not path.exists():
        return {"loaded": 0, "alerts": 0, "error": f"File not found: {path}"}

    loaded = 0
    alerts_generated = 0
    all_alerts = []

    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
                event = normalizer(raw)
                store.append(event.model_dump())
                new_alerts = rule_engine(event)
                all_alerts.extend(a.model_dump() for a in new_alerts)
                alerts_generated += len(new_alerts)
                loaded += 1
            except Exception:
                continue

    return {"loaded": loaded, "alerts": alerts_generated, "events": store, "alert_list": all_alerts}
