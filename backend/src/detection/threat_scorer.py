"""Threat scoring model — Phase 5.

score_alert: additive 0-100 model combining:
  + suricata_severity_points (critical=40, high=30, medium=20, low=10)
  + sigma_hit: +20 if alert.rule matches UUID pattern (sigma-sourced alert)
  + recurrence: +10 if same host/IP seen >= 3 times in events list
  + graph_connectivity: +10 if graph_data provided and host/IP has >= 3 alert edges
Score is capped at 100.
"""


def score_alert(alert, events: list[dict], graph_data: dict | None = None) -> int:
    """Compute threat score 0-100.

    Not yet implemented — raises NotImplementedError until Plan 02.
    """
    raise NotImplementedError("score_alert not implemented — see Plan 02")
