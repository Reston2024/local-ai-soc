"""
FeedbackClassifier — River LogisticRegression for online TP/FP classification.

Each analyst verdict calls learn_one() which updates the model immediately
and persists state to disk. Provides predict_proba_tp() for scoring and
accuracy() once >= 10 samples have been collected.

Model persistence uses joblib (preferred) falling back to a JSON state dict
if joblib is unavailable. Models are local-process-only — no untrusted
deserialization.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from backend.core.logging import get_logger

log = get_logger(__name__)

_DEFAULT_MODEL_DIR = "data/models"
_MODEL_FILENAME = "feedback_classifier.bin"
_MIN_SAMPLES_FOR_ACCURACY = 10


class FeedbackClassifier:
    """Online TP/FP classifier backed by River LogisticRegression.

    Args:
        model_dir: Directory where the model file is persisted.
                   Defaults to ``data/models``.
    """

    def __init__(self, model_dir: str | Path = _DEFAULT_MODEL_DIR) -> None:
        from river.linear_model import LogisticRegression
        from river.metrics import Accuracy

        self._model_dir = Path(model_dir)
        self._model_dir.mkdir(parents=True, exist_ok=True)
        self._model_path = self._model_dir / _MODEL_FILENAME

        self._model = LogisticRegression()
        self._metric = Accuracy()
        self._n_samples: int = 0

        # Attempt to restore a previously saved model (auto-load on init)
        self._load_or_create()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def n_samples(self) -> int:
        """Number of samples seen so far."""
        return self._n_samples

    def learn_one(self, features: dict, verdict: str) -> None:
        """Update the model with one analyst verdict.

        Args:
            features: Feature dict (severity, rule_id_hash, etc.).
            verdict:  ``"TP"`` or ``"FP"``.
        """
        label = 1 if verdict == "TP" else 0

        # Update running accuracy metric before learning (online evaluation)
        pred = self._model.predict_one(features)
        if pred is not None:
            self._metric.update(label, pred)

        # Supervised update
        self._model.learn_one(features, label)
        self._n_samples += 1

        # Persist immediately so sessions never lose state
        self._save()

    def predict_proba_tp(self, features: dict) -> float:
        """Return estimated probability that this detection is a True Positive.

        Returns:
            Float in [0.0, 1.0]. Returns 0.5 for an untrained model.
        """
        probas = self._model.predict_proba_one(features)
        if probas is None:
            return 0.5
        return float(probas.get(1, 0.5))

    def accuracy(self) -> Optional[float]:
        """Return running accuracy, or ``None`` if fewer than 10 samples seen.

        This prevents misleading "100% from 1 sample" early readings.
        """
        if self._n_samples < _MIN_SAMPLES_FOR_ACCURACY:
            return None
        return round(self._metric.get(), 4)

    def save(self) -> None:
        """Explicitly save the current model state to disk."""
        self._save()

    def load(self) -> None:
        """Explicitly reload the model state from disk."""
        self._load_or_create()

    # ------------------------------------------------------------------
    # Internal persistence helpers
    # ------------------------------------------------------------------

    def _save(self) -> None:
        """Persist model to disk using joblib (preferred) or JSON fallback."""
        try:
            import joblib  # type: ignore[import]
            joblib.dump(
                {
                    "model": self._model,
                    "metric": self._metric,
                    "n_samples": self._n_samples,
                },
                str(self._model_path),
            )
            log.debug("FeedbackClassifier saved (joblib)", path=str(self._model_path))
        except ImportError:
            # Minimal JSON fallback — preserves sample count but not full model
            import json
            self._model_path.write_text(json.dumps({"n_samples": self._n_samples}))
            log.debug("FeedbackClassifier saved (json fallback)", path=str(self._model_path))
        except Exception as exc:
            log.warning("FeedbackClassifier save failed (non-fatal): %s", exc)

    def _load_or_create(self) -> None:
        """Load model from disk if available, otherwise start fresh."""
        if not self._model_path.exists():
            return  # fresh start — model already initialised in __init__

        try:
            import joblib  # type: ignore[import]
            state = joblib.load(str(self._model_path))
            if isinstance(state, dict) and "model" in state:
                self._model = state["model"]
                self._metric = state.get("metric", self._metric)
                self._n_samples = state.get("n_samples", 0)
                log.info(
                    "FeedbackClassifier loaded (joblib)",
                    n_samples=self._n_samples,
                )
                return
        except ImportError:
            pass  # fall through to JSON path
        except Exception as exc:
            log.warning("FeedbackClassifier joblib load failed, resetting: %s", exc)
            return

        # JSON fallback — restore n_samples only, model starts fresh
        try:
            import json
            state = json.loads(self._model_path.read_text())
            self._n_samples = state.get("n_samples", 0)
            log.info(
                "FeedbackClassifier loaded (json fallback)",
                n_samples=self._n_samples,
            )
        except Exception as exc:
            log.warning("FeedbackClassifier json load failed, resetting: %s", exc)
