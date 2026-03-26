"""LLM explanation engine — evidence serialization + grounded Ollama calls."""
import logging
import re
from typing import Any

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a cybersecurity analyst assistant. "
    "CRITICAL: You MUST only use the evidence provided below. "
    "Do NOT invent, assume, or hallucinate any facts not present in the evidence. "
    "If the evidence does not support a statement, write 'insufficient evidence'."
)

_SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}


def build_evidence_context(investigation: dict, max_events: int = 10) -> str:
    """Serialize an investigation result into a grounded evidence block for the LLM."""
    lines: list[str] = []

    # 1. Detection metadata
    detection = investigation.get("detection") or {}
    if detection:
        lines.append(
            f"DETECTION: {detection.get('rule_name', 'Unknown')} | "
            f"severity={detection.get('severity', 'info')} | "
            f"technique={detection.get('attack_technique', 'N/A')} | "
            f"tactic={detection.get('attack_tactic', 'N/A')}"
        )

    # 2. Top N events by severity (most severe first)
    raw_events = investigation.get("events") or []
    sorted_events = sorted(
        raw_events,
        key=lambda e: _SEVERITY_ORDER.get(e.get("severity") or "info", 0),
        reverse=True,
    )[:max_events]
    for evt in sorted_events:
        lines.append(
            f"EVENT: {evt.get('timestamp', '?')} | "
            f"{evt.get('event_type', '?')} | "
            f"process={evt.get('process_name', '?')} | "
            f"host={evt.get('hostname', '?')} | "
            f"technique={evt.get('attack_technique', 'N/A')}"
        )

    # 3. Unique MITRE techniques
    techniques = investigation.get("techniques") or []
    technique_ids = [t.get("technique_id") for t in techniques if t.get("technique_id")]
    if technique_ids:
        lines.append(f"MITRE TECHNIQUES: {', '.join(technique_ids)}")

    # 4. Graph summary
    nodes = (investigation.get("graph") or {}).get("elements", {}).get("nodes") or []
    timeline = investigation.get("timeline") or []
    lines.append(f"GRAPH: {len(nodes)} entities | {len(timeline)} timeline events")

    return "\n".join(lines)


def _parse_explanation_sections(raw_text: str) -> dict[str, str]:
    """Parse the three-section Ollama response into a structured dict."""
    sections = {
        "what_happened": "insufficient evidence",
        "why_it_matters": "insufficient evidence",
        "recommended_next_steps": "insufficient evidence",
    }
    # Match ## What Happened, ## Why It Matters, ## Recommended Next Steps
    pattern = re.compile(
        r"##\s*What Happened\s*\n(.*?)(?=##\s*Why It Matters|$)"
        r"|##\s*Why It Matters\s*\n(.*?)(?=##\s*Recommended Next Steps|$)"
        r"|##\s*Recommended Next Steps\s*\n(.*?)(?=##|$)",
        re.DOTALL | re.IGNORECASE,
    )
    for m in pattern.finditer(raw_text):
        if m.group(1) is not None:
            sections["what_happened"] = m.group(1).strip()
        elif m.group(2) is not None:
            sections["why_it_matters"] = m.group(2).strip()
        elif m.group(3) is not None:
            sections["recommended_next_steps"] = m.group(3).strip()
    return sections


async def generate_explanation(
    investigation: dict,
    ollama_client: Any,
    model: str = "qwen3:14b",
) -> dict[str, str]:
    """Generate a three-section explanation grounded in evidence.

    Args:
        investigation: The investigation result dict (from /api/investigate or assembled dict).
        ollama_client: An OllamaClient instance.
        model: Ollama model to use (default: qwen3:14b per user decision).

    Returns:
        Dict with keys: what_happened, why_it_matters, recommended_next_steps.
    """
    context = build_evidence_context(investigation)
    prompt = (
        f"Based ONLY on the following evidence, provide a structured analysis:\n\n"
        f"{context}\n\n"
        f"Respond with exactly three sections:\n"
        f"## What Happened\n"
        f"[Describe the attack chain step by step, citing specific processes and timestamps]\n\n"
        f"## Why It Matters\n"
        f"[Explain the MITRE technique impact and business risk, citing specific technique IDs]\n\n"
        f"## Recommended Next Steps\n"
        f"[List 3-5 concrete containment and investigation actions based on the evidence]"
    )

    raw_response = await ollama_client.generate(
        prompt=prompt,
        system=_SYSTEM_PROMPT,
        temperature=0.1,
        model=model,
    )
    return _parse_explanation_sections(raw_response or "")
