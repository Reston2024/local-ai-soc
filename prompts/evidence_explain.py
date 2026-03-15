"""
Prompts for explaining individual security events in plain language.

Given a raw event (JSON or formatted text), the LLM describes what happened,
why it might be suspicious or notable, and what context an analyst needs to
assess the event's significance.
"""

from __future__ import annotations

SYSTEM = """You are a cybersecurity expert explaining security log events to analysts.
When given a raw security event, you:
1. Describe what the event represents in plain English.
2. Explain the security relevance — why this type of event is significant.
3. Identify any suspicious or anomalous indicators within the event itself.
4. Suggest what follow-up events or data an analyst should look for.
5. Reference the relevant MITRE ATT&CK technique if applicable.

Tone: Technical but clear. Assume the analyst has security knowledge but
may not be familiar with every Windows event ID or log format.
Be specific — reference actual field values from the event, not generic descriptions.
Do NOT over-alert on benign events; acknowledge when an event is likely routine."""


def build_prompt(
    raw_event: str,
    event_type: str | None = None,
    hostname: str | None = None,
    username: str | None = None,
    additional_context: str | None = None,
) -> str:
    """
    Build a prompt for explaining a single security event.

    Args:
        raw_event:          The raw event content — JSON string, XML snippet,
                            or any text representation of the event.
        event_type:         Optional event type hint (e.g. "process_create",
                            "network_connect") to help the LLM contextualise.
        hostname:           Optional hostname for additional context.
        username:           Optional username for additional context.
        additional_context: Optional free-text context (e.g., "This host is a
                            domain controller" or "User is a service account").

    Returns:
        Formatted prompt string for the user turn.
    """
    context_lines = []
    if event_type:
        context_lines.append(f"Event Type: {event_type}")
    if hostname:
        context_lines.append(f"Hostname: {hostname}")
    if username:
        context_lines.append(f"Username: {username}")
    if additional_context:
        context_lines.append(f"Additional Context: {additional_context}")

    context_block = ""
    if context_lines:
        context_block = "\n".join(context_lines) + "\n\n"

    instructions = (
        "\n\nPlease explain this event in plain language, covering:\n"
        "1. WHAT HAPPENED — What does this event record?\n"
        "2. SECURITY RELEVANCE — Why do analysts care about this event type?\n"
        "3. SUSPICIOUS INDICATORS — Are there specific field values that look unusual?\n"
        "4. FOLLOW-UP STEPS — What should the analyst check next?\n"
        "5. ATT&CK MAPPING — Does this event match a known ATT&CK technique? (if applicable)"
    )

    return f"{context_block}[RAW EVENT]\n{raw_event}\n[/RAW EVENT]{instructions}"
