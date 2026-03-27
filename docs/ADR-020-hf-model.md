# ADR-020: Cybersecurity-Specialised LLM Selection

**Status:** Accepted
**Date:** 2026-03-27
**Deciders:** AI-SOC-Brain architecture team

---

## Context

The system currently uses `qwen3:14b` (general-purpose) for all LLM tasks including triage,
analyst Q&A, and investigation summaries.  Cybersecurity investigation work benefits from a
domain-specialised model that has been pre-trained or fine-tuned on security corpora (CVEs,
threat reports, MITRE ATT&CK, malware analysis, etc.).

Two candidates from Hugging Face were shortlisted based on public reputation, GGUF availability
for Ollama, and community adoption:

1. **Foundation-Sec-8B** — `fdtn-ai/Foundation-Sec-8B`
2. **Seneca-Cybersecurity-LLM** — `AlicanKiraz0/Seneca-Cybersecurity-LLM`

Hardware target: NVIDIA RTX 5080 (16 GB GDDR7), Windows 11, running Ollama locally.
`qwen3:14b` at Q4_K_M occupies approximately 9 GB VRAM, leaving ~7 GB for a second model.

---

## Candidate Evaluation

### Candidate 1: Foundation-Sec-8B (`fdtn-ai/Foundation-Sec-8B`)

| Criterion | Finding |
|-----------|---------|
| Publisher | Cisco Foundation AI research team (`fdtn-ai` org) |
| Parameters | 8 B |
| Base model | Llama-3.1-8B (Meta) |
| Licence | Apache 2.0 — commercial-permissive |
| Training data provenance | Documented: public security corpora including NVD, MITRE ATT&CK, threat intel reports, malware analysis papers; described in Cisco Foundation AI technical blog |
| GGUF / Ollama availability | Yes — Q4_K_M, Q5_K_M, Q8_0 variants published on HF and Ollama registry (`foundation-sec:8b`) |
| Known CVEs / jailbreak reports | None found in HF Discussions or public CVE feeds as of evaluation date |
| Prompt injection risk | Standard LLM risk profile; no adversarial embedding attacks specific to this model reported |
| Community footprint | ~1 k downloads/month at evaluation; active Cisco research backing |
| Maintenance status | Actively maintained — weights and GGUF variants updated alongside Llama-3.1 ecosystem |

### Candidate 2: Seneca-Cybersecurity-LLM (`AlicanKiraz0/Seneca-Cybersecurity-LLM`)

| Criterion | Finding |
|-----------|---------|
| Publisher | Individual contributor (`AlicanKiraz0`) |
| Parameters | Variable (base model size not clearly documented on model card) |
| Base model | Undisclosed / partially documented |
| Licence | Not clearly stated on HF model card; defaults to HF community licence (non-commercial restriction risk) |
| Training data provenance | Minimal documentation — references generic cybersecurity Q&A datasets without citation |
| GGUF / Ollama availability | Limited — no first-party GGUF; community-converted versions unverified |
| Known CVEs / jailbreak reports | No dedicated CVE entries; insufficient community exposure to surface issues |
| Prompt injection risk | Unknown — no published safety evaluation |
| Community footprint | Low (<100 downloads/month); no institutional backing |
| Maintenance status | Infrequent updates; uncertain long-term support |

---

## Security Scan Summary

| Model | Licence | Provenance | Known Vulns | Publisher Trust | Prompt Injection Risk |
|-------|---------|------------|-------------|-----------------|----------------------|
| Foundation-Sec-8B | Apache 2.0 (permissive) | Well-documented (Cisco) | None found | High (institutional) | Standard LLM baseline |
| Seneca-Cybersecurity-LLM | Unclear | Poorly documented | Unknown | Low (individual) | Unknown |

---

## Hardware Fit Analysis (RTX 5080, 16 GB VRAM)

| Model | Params | Quantisation | Est. VRAM | Fits GPU | Est. tokens/s | Notes |
|-------|--------|--------------|-----------|----------|---------------|-------|
| qwen3:14b (existing) | 14 B | Q4_K_M | ~9.0 GB | Yes | ~35 t/s | General-purpose model; always loaded |
| Foundation-Sec-8B Q4_K_M | 8 B | Q4_K_M | ~4.8 GB | Yes | ~55 t/s | Fits within remaining ~7 GB headroom |
| Foundation-Sec-8B Q5_K_M | 8 B | Q5_K_M | ~5.5 GB | Yes | ~50 t/s | Higher quality; still fits |
| Foundation-Sec-8B Q8_0 | 8 B | Q8_0 | ~8.5 GB | Marginal | ~40 t/s | Would require qwen3 unload |
| Seneca-Cybersecurity-LLM | N/A | N/A | TBD | TBD | TBD | Undocumented base; not evaluated further |

VRAM estimate methodology: Q4_K_M ~0.6 GB/B parameters + ~0.5 GB overhead (KV cache, runtime).
Recommended quantisation: **Q4_K_M** — optimal quality/VRAM balance; both models coexist simultaneously.

---

## Decision

**Selected model: Foundation-Sec-8B at Q4_K_M quantisation (`foundation-sec:8b`)**

Rationale:

1. **Institutional provenance** — Cisco Foundation AI is a credible, accountable publisher with
   documented training methodology. Training data sourcing is transparent.
2. **Apache 2.0 licence** — Commercial-permissive; no restrictions on use in this system.
3. **Hardware fit** — 8B Q4_K_M (~4.8 GB) sits comfortably within the ~7 GB remaining VRAM
   alongside `qwen3:14b`, enabling simultaneous model serving with no swapping.
4. **Ollama-native** — First-party GGUF published directly to Ollama registry; `ollama pull`
   works out of the box.
5. **Domain specialisation** — Trained on NVD, MITRE ATT&CK, and security corpora; expected to
   outperform qwen3:14b on CVE explanation, IOC triage, and analyst Q&A tasks.
6. **Active maintenance** — Tracks Llama-3.1 ecosystem updates; long-term viability assured.

Seneca-Cybersecurity-LLM was **rejected** due to unclear licence, undocumented training data,
individual (non-institutional) publisher, and absent GGUF support.

---

## Consequences

### Required changes

- Add `OLLAMA_CYBERSEC_MODEL` environment variable to `backend/core/config.py` Settings:
  ```python
  OLLAMA_CYBERSEC_MODEL: str = "foundation-sec:8b"
  ```
- Document the variable in `.env.example` with the pull command.

### Operational

- Operators must pull the model before first use:
  ```bash
  ollama pull foundation-sec:8b
  ```
- The model will be used for: investigation summaries, triage prompts, analyst Q&A routing.
- The existing `qwen3:14b` flow (`OLLAMA_MODEL`) is **unchanged** — no breaking changes.
- Embedding model (`mxbai-embed-large`, `OLLAMA_EMBED_MODEL`) is unchanged.

### Routing strategy (implemented in Plan 02)

- Cybersec-domain requests route to `OLLAMA_CYBERSEC_MODEL`.
- General/fallback requests continue to use `OLLAMA_MODEL` (`qwen3:14b`).
- Model selection is configurable at runtime via environment variable.

---

## References

- [Foundation-Sec-8B on Hugging Face](https://huggingface.co/fdtn-ai/Foundation-Sec-8B)
- [Cisco Foundation AI technical blog](https://blogs.cisco.com/security/introducing-foundation-sec-8b)
- [Ollama model library — foundation-sec](https://ollama.com/library/foundation-sec)
- [MITRE ATT&CK Framework](https://attack.mitre.org/)
- Related ADRs: ADR-001 (Ollama integration), ADR-005 (embedding model selection)
