"""
Prompts for detection triage — prioritising and explaining a set of alerts.

Given a list of detection summaries, the LLM explains what is most critical,
why it matters, and what the analyst should do next.
"""

from __future__ import annotations

SYSTEM = """You are an expert cybersecurity analyst performing alert triage.
You will be given a list of security detections from an automated detection engine.
Your task is to:
1. Identify the most critical findings and explain why they are high priority.
2. Group related detections that likely represent a single attack chain.
3. Recommend specific next steps for the analyst to investigate further.
4. Clearly state what you are uncertain about.

Rules:
- Base your analysis ONLY on the detections provided.
- Do NOT invent additional context or IOCs not present in the input.
- Be concise — analysts are busy. Lead with the most important finding.
- Use MITRE ATT&CK technique IDs (e.g. T1059.001) when you can identify them.
- Clearly separate facts (observed) from inference (likely / possibly)."""


def build_prompt(
    detections: list[str],
    case_id: str | None = None,
    context_events: list[str] | None = None,
) -> str:
    """
    Build a triage prompt.

    Args:
        detections:     List of detection summary strings.  Each entry should
                        describe one detection (rule name, severity, matched
                        events, ATT&CK mappings, etc.).
        case_id:        Optional case identifier for context.
        context_events: Optional list of raw event strings to provide extra
                        supporting evidence.

    Returns:
        Formatted prompt string for the user turn.
    """
    if not detections:
        return "No detections were provided. Please supply detection data for triage."

    detection_block = "\n\n".join(
        f"[DETECTION {i + 1}]\n{d}\n[/DETECTION {i + 1}]"
        for i, d in enumerate(detections)
    )

    case_context = f"Case ID: {case_id}\n\n" if case_id else ""

    events_block = ""
    if context_events:
        events_block = "\n\nSupporting Events:\n" + "\n\n".join(
            f"[EVENT]\n{e}\n[/EVENT]" for e in context_events
        )

    instructions = (
        "\n\nBased on the detections above, provide a structured triage report with:\n"
        "1. CRITICAL FINDINGS — What is the most serious alert and why?\n"
        "2. RELATED DETECTIONS — Which alerts are likely part of the same attack?\n"
        "3. RECOMMENDED NEXT STEPS — What should the analyst investigate first?\n"
        "4. UNCERTAINTY — What do you not know / cannot determine from the evidence?"
    )

    return f"{case_context}{detection_block}{events_block}{instructions}"
