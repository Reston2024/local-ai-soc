"""
Launcher for the SOC Reranker microservice (BAAI/bge-reranker-v2-m3).

WHY THIS LAUNCHER EXISTS:
    torch with CUDA support requires a platform-specific wheel that cannot be
    listed in pyproject.toml without breaking CPU-only CI environments.
    This script checks for torch presence, prints installation instructions
    if absent, and launches the FastAPI app via uvicorn.

INSTALL CUDA TORCH (one-time setup, not in pyproject.toml):
    pip install torch --index-url https://download.pytorch.org/whl/cu121
    pip install transformers sentencepiece

    OR for CUDA 12.8+ (RTX 5080 / Blackwell):
    pip install torch --index-url https://download.pytorch.org/whl/cu128

USAGE:
    uv run python scripts/start_reranker.py

The service starts on http://0.0.0.0:8100
Verify: curl http://127.0.0.1:8100/health
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Check torch is installed
# ---------------------------------------------------------------------------
try:
    import torch  # noqa: F401
except ImportError:
    print(
        "\n[ERROR] torch is not installed. The reranker service requires torch.\n"
        "\nInstall CUDA-enabled torch manually:\n"
        "    pip install torch --index-url https://download.pytorch.org/whl/cu121\n"
        "    pip install transformers sentencepiece\n"
        "\nFor RTX 5080 / Blackwell (CUDA 12.8+):\n"
        "    pip install torch --index-url https://download.pytorch.org/whl/cu128\n"
        "    pip install transformers sentencepiece\n"
        "\nNOTE: torch is NOT in pyproject.toml to avoid breaking CPU-only CI.",
        file=sys.stderr,
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Warn if CUDA is not available (but continue -- CPU inference still works)
# ---------------------------------------------------------------------------
if not torch.cuda.is_available():
    print(
        "\n[WARNING] CUDA not available -- reranker will run on CPU (slower).\n"
        "For GPU inference, ensure CUDA drivers are installed and torch was built\n"
        "with CUDA support. On RTX 5080 (Blackwell), use CUDA 12.8+.\n",
        file=sys.stderr,
    )

# ---------------------------------------------------------------------------
# Launch the FastAPI app
# ---------------------------------------------------------------------------
import uvicorn  # noqa: E402

if __name__ == "__main__":
    print("[*] Starting SOC Reranker on http://0.0.0.0:8100")
    uvicorn.run(
        "backend.services.reranker_service:app",
        host="0.0.0.0",
        port=8100,
        reload=False,
    )
