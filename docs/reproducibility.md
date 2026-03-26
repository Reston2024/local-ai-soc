# Reproducibility

> This document redirects to the canonical reproducibility record.

The build reproducibility information for AI-SOC-Brain is maintained in:

**[REPRODUCIBILITY_RECEIPT.md](../REPRODUCIBILITY_RECEIPT.md)** (repository root)

That file contains:
- Python and dependency versions (pinned via `uv.lock`)
- Ollama version and model hashes
- Docker and Caddy versions
- Frontend dependency versions (Svelte, Vite, Cytoscape, D3)
- pip-audit baseline
- Verification status

## Quick Reference

To verify your environment matches the receipt:

```bash
# Check Python version
uv run python --version

# Check all pinned packages match
uv run pip list --format=freeze | sort

# Run dependency audit
uv run pip-audit --desc
```

*Last updated: 2026-03-26*
