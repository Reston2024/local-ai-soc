"""
Prompts for analyst Q&A — answering free-form questions about evidence.

The LLM is instructed to answer ONLY from provided context, cite event IDs,
and refuse to speculate beyond the evidence.
"""

from __future__ import annotations

SYSTEM = """You are an AI assistant helping a cybersecurity analyst investigate security events.
You have access to evidence from the analyst's local investigation platform.
IMPORTANT: Answer ONLY based on the provided context below.
If the context does not contain enough information to answer the question, say so explicitly.
Do NOT speculate, invent IOCs, or make claims not supported by the evidence.
Always cite specific event IDs when referencing evidence."""


def build_prompt(
    question: str,
    context_events: list[str],
    context_notes: list[str] | None = None,
) -> str:
    """
    Build a prompt for analyst Q&A.

    Args:
        question:       The analyst's natural-language question.
        context_events: List of event text strings (one per retrieved event).
                        Each should be a readable representation of a
                        NormalizedEvent (e.g. from to_embedding_text() or
                        a formatted JSON dump).
        context_notes:  Optional list of analyst note strings to include
                        as additional context.

    Returns:
        A formatted prompt string ready to pass to the LLM as the user turn.
        The SYSTEM string should be passed separately as the system prompt.
    """
    if not context_events:
        context = "[No evidence retrieved for this query]"
    else:
        context = "\n\n".join(
            f"[EVIDENCE]\n{e}\n[/EVIDENCE]" for e in context_events
        )

    if context_notes:
        notes_section = "\n\n".join(
            f"[ANALYST NOTE]\n{n}\n[/ANALYST NOTE]" for n in context_notes
        )
        context = context + "\n\n" + notes_section

    return f"{context}\n\nQuestion: {question}"
