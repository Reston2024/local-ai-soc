"""
Prompts for hypothesis-driven threat hunting.

The analyst provides a hypothesis (e.g., "An attacker may have used Cobalt
Strike beacons on the finance segment").  The LLM reviews provided evidence
to find supporting or refuting indicators and maps them to ATT&CK techniques.
"""

from __future__ import annotations

SYSTEM = """You are a threat hunter with deep expertise in Windows security,
MITRE ATT&CK, and incident response.
You are given a threat hunting hypothesis and a collection of security events
and detections from the environment.

Your task is to:
1. Review the evidence for indicators that SUPPORT the hypothesis.
2. Review the evidence for indicators that REFUTE the hypothesis.
3. Identify ATT&CK techniques (with IDs) observed in the evidence.
4. Recommend specific artifacts or data sources to check next.
5. Assign a confidence level: HIGH / MEDIUM / LOW to the hypothesis.

Rules:
- Only reference specific events by their event_id when citing evidence.
- Clearly distinguish between "observed" and "inferred" findings.
- If evidence is insufficient to evaluate the hypothesis, say so.
- Do NOT fabricate events or IOCs.
- Structure your response with clear headings for each section."""


def build_prompt(
    hypothesis: str,
    context_events: list[str],
    existing_detections: list[str] | None = None,
    case_id: str | None = None,
) -> str:
    """
    Build a threat hunt prompt.

    Args:
        hypothesis:          The hunt hypothesis as a natural-language string.
                             E.g., "Lateral movement via PsExec occurred on
                             the 10.0.1.0/24 subnet between 14:00 and 16:00."
        context_events:      Retrieved event strings relevant to the hypothesis.
        existing_detections: Optional list of existing detection summaries that
                             may support or contradict the hypothesis.
        case_id:             Optional case ID for context.

    Returns:
        Formatted prompt string for the user turn.
    """
    if not context_events and not existing_detections:
        return (
            f"Hypothesis: {hypothesis}\n\n"
            "No evidence was found in the current dataset to evaluate this hypothesis. "
            "Consider expanding the time range or importing additional data sources."
        )

    case_context = f"Case ID: {case_id}\n\n" if case_id else ""

    events_block = ""
    if context_events:
        events_block = "Evidence from event store:\n\n" + "\n\n".join(
            f"[EVENT]\n{e}\n[/EVENT]" for e in context_events
        )

    detections_block = ""
    if existing_detections:
        detections_block = "\n\nExisting Detections:\n\n" + "\n\n".join(
            f"[DETECTION]\n{d}\n[/DETECTION]" for d in existing_detections
        )

    instructions = (
        "\n\nBased on the evidence above, evaluate the following hypothesis:\n\n"
        f"HYPOTHESIS: {hypothesis}\n\n"
        "Provide your analysis structured as:\n"
        "1. EVIDENCE FOR — Specific events/detections supporting the hypothesis\n"
        "2. EVIDENCE AGAINST — Specific events/detections refuting the hypothesis\n"
        "3. ATT&CK TECHNIQUES OBSERVED — Technique IDs and descriptions seen in evidence\n"
        "4. RECOMMENDED NEXT STEPS — What data sources or queries to run next\n"
        "5. CONFIDENCE LEVEL — HIGH / MEDIUM / LOW with justification"
    )

    return f"{case_context}{events_block}{detections_block}{instructions}"
