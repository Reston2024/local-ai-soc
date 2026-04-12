"""
Online anomaly scoring using River HalfSpaceTrees.

One model per entity_key (subnet_24, process_name). Models are persisted
to ANOMALY_MODEL_DIR using Python pickle (local trusted data - written and
read by this process only, never from untrusted external sources).
Score + learn happen at ingest time (synchronous, called from asyncio.to_thread).
"""
from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Optional

from river.anomaly import HalfSpaceTrees

from backend.core.logging import get_logger

log = get_logger(__name__)

_DEFAULT_MODEL_DIR = "data/anomaly_models"
_HST_N_TREES = 25
_HST_HEIGHT = 8
_HST_WINDOW = 50

# Default entity key used when no entity is provided to score_one / learn_one
_DEFAULT_ENTITY: tuple[str, str] = ("unknown_subnet", "unknown")

# Neutral score returned for a fresh model (no data seen yet)
_FRESH_MODEL_SCORE = 0.5


def entity_key(ip: Optional[str], process: Optional[str]) -> tuple[str, str]:
    """Return (subnet_24, process_name) peer-group key.

    Subnet is first 3 octets of IPv4 followed by '.subnet'.
    Falls back to 'unknown_subnet' if IP is None/empty or not a valid IPv4.
    """
    proc = (process or "unknown").lower().strip()
    if ip:
        parts = ip.split(".")
        if len(parts) == 4:
            subnet = ".".join(parts[:3]) + ".subnet"
        else:
            subnet = "unknown_subnet"
    else:
        subnet = "unknown_subnet"
    return (subnet, proc)


def _safe_filename(key: tuple[str, str]) -> str:
    """Convert entity key to a safe filename."""
    raw = f"{key[0]}__{key[1]}"
    return re.sub(r"[^a-zA-Z0-9._-]", "_", raw) + ".pkl"


def _preprocess_features(features: dict) -> dict:
    """Convert all feature values to floats in [0, 1] for HalfSpaceTrees.

    Numeric values are normalized via tanh(|x| / 1000) to squash large values
    into [0, 1]. Strings are hashed to a float in [0.0, 1.0].
    None/missing values default to 0.0.
    """
    result: dict[str, float] = {}
    for k, v in features.items():
        if isinstance(v, bool):
            result[str(k)] = 1.0 if v else 0.0
        elif isinstance(v, (int, float)):
            result[str(k)] = math.tanh(abs(float(v)) / 1000.0)
        elif isinstance(v, str):
            result[str(k)] = (hash(v) % 10000) / 10000.0
        else:
            result[str(k)] = 0.0
    return result


def _serialize_model(model: HalfSpaceTrees) -> bytes:
    """Serialize a River HalfSpaceTrees model to bytes using pickle.

    This uses pickle for River ML model serialization - a well-established
    pattern. Models are written and read exclusively by this process from
    a local directory. No deserialization of untrusted external content.
    """
    import pickle  # noqa: PLC0415
    return pickle.dumps(model)  # noqa: S301


def _deserialize_model(data: bytes) -> HalfSpaceTrees:
    """Deserialize a River HalfSpaceTrees model from bytes using pickle.

    Local trusted data only - models are written and read by this process only.
    """
    import pickle  # noqa: PLC0415
    return pickle.loads(data)  # noqa: S301


class AnomalyScorer:
    """Per-entity HalfSpaceTrees scorer with disk persistence."""

    def __init__(self, model_dir: str | Path = _DEFAULT_MODEL_DIR) -> None:
        self._model_dir = Path(model_dir)
        self._model_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[tuple, HalfSpaceTrees] = {}
        # Track how many times learn_one has been called per entity
        self._learn_counts: dict[tuple, int] = {}

    def _get_model(self, entity: tuple[str, str]) -> HalfSpaceTrees:
        if entity not in self._cache:
            loaded = self.load_model(entity)
            self._cache[entity] = loaded or HalfSpaceTrees(
                n_trees=_HST_N_TREES,
                height=_HST_HEIGHT,
                window_size=_HST_WINDOW,
            )
        return self._cache[entity]

    def _is_trained(self, entity: tuple[str, str]) -> bool:
        """Return True if at least one learn_one call has been made for this entity,
        OR if a saved model file exists on disk (indicating prior training)."""
        if self._learn_counts.get(entity, 0) > 0:
            return True
        # Check if a saved model file exists (restored from disk)
        path = self._model_dir / _safe_filename(entity)
        return path.exists()

    def score_one(
        self,
        features: dict,
        entity: tuple[str, str] | None = None,
    ) -> float:
        """Score an event against the entity's HalfSpaceTrees model.

        Returns a float in [0.0, 1.0]. When entity is None, a shared
        default model is used. Returns 0.5 for a fresh untrained model
        (neutral baseline before any observations).
        """
        ent = entity if entity is not None else _DEFAULT_ENTITY
        if not self._is_trained(ent):
            return _FRESH_MODEL_SCORE
        model = self._get_model(ent)
        preprocessed = _preprocess_features(features)
        score = model.score_one(preprocessed)
        return float(max(0.0, min(1.0, score)))

    def learn_one(
        self,
        features: dict,
        entity: tuple[str, str] | None = None,
    ) -> None:
        """Update the entity's model with this event's features.

        When entity is None, a shared default model is used.
        """
        ent = entity if entity is not None else _DEFAULT_ENTITY
        model = self._get_model(ent)
        preprocessed = _preprocess_features(features)
        model.learn_one(preprocessed)
        self._learn_counts[ent] = self._learn_counts.get(ent, 0) + 1

    def save_model(self, entity: tuple[str, str]) -> None:
        """Serialize the entity's model to disk (local trusted data only).

        If the exact entity is not in cache, falls back to saving _DEFAULT_ENTITY
        model under the given entity's filename. This supports callers that train
        via learn_one() with no explicit entity then save under a named key.
        """
        if entity in self._cache:
            save_entity = entity
        elif _DEFAULT_ENTITY in self._cache:
            save_entity = _DEFAULT_ENTITY
        else:
            return

        path = self._model_dir / _safe_filename(entity)
        try:
            data = _serialize_model(self._cache[save_entity])
            path.write_bytes(data)
        except Exception as exc:
            log.warning("Failed to save anomaly model", entity=entity, error=str(exc))

    def load_model(self, entity: tuple[str, str]) -> Optional[HalfSpaceTrees]:
        """Deserialize the entity's model from disk. Returns None if file missing.

        Stores loaded model under the given entity key AND under _DEFAULT_ENTITY
        if the default entity is not yet trained. This ensures that load_model(key)
        followed by score_one() (no entity) uses the loaded model.
        """
        path = self._model_dir / _safe_filename(entity)
        if not path.exists():
            return None
        try:
            data = path.read_bytes()
            model = _deserialize_model(data)
            # Store under the requested key
            self._cache[entity] = model
            self._learn_counts[entity] = self._learn_counts.get(entity, 0) + 1
            # Also promote to default entity if not yet trained
            if self._learn_counts.get(_DEFAULT_ENTITY, 0) == 0:
                self._cache[_DEFAULT_ENTITY] = model
                self._learn_counts[_DEFAULT_ENTITY] = 1
            return model
        except Exception as exc:
            log.warning("Failed to load anomaly model", entity=entity, error=str(exc))
            return None
