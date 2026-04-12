"""
Wave 0 TDD stubs for Phase 44 FeedbackClassifier.
P44-T02: River online learning, learn_one, accuracy, save/load, predict_proba_tp.
P44-T03: Accuracy hidden below 10 samples, visible at 10+.

One RED import test (test_import_feedback_classifier) runs immediately and
fails until Plan 44-02 creates backend/services/feedback/classifier.py.
All other behavioral stubs skip cleanly.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

_skip = pytest.mark.skip(reason="stub — implemented in Plan 44-02")


# ---------------------------------------------------------------------------
# Test 0 — RED import test (NO skip decorator)
# Must fail until Plan 44-02 creates backend/services/feedback/classifier.py
# ---------------------------------------------------------------------------
def test_import_feedback_classifier():
    from backend.services.feedback.classifier import FeedbackClassifier  # noqa: F401


# ---------------------------------------------------------------------------
# Stub 1 — learn_one TP increments n_samples to 1
# ---------------------------------------------------------------------------
@_skip
def test_learn_one_tp():
    from backend.services.feedback.classifier import FeedbackClassifier
    clf = FeedbackClassifier()
    clf.learn_one({"severity": 3, "rule_id_hash": 1}, "TP")
    assert clf.n_samples == 1


# ---------------------------------------------------------------------------
# Stub 2 — learn_one FP increments n_samples to 1
# ---------------------------------------------------------------------------
@_skip
def test_learn_one_fp():
    from backend.services.feedback.classifier import FeedbackClassifier
    clf = FeedbackClassifier()
    clf.learn_one({"severity": 1, "rule_id_hash": 2}, "FP")
    assert clf.n_samples == 1


# ---------------------------------------------------------------------------
# Stub 3 — accuracy() returns None below 10 samples
# ---------------------------------------------------------------------------
@_skip
def test_accuracy_hidden_below_10():
    from backend.services.feedback.classifier import FeedbackClassifier
    clf = FeedbackClassifier()
    for i in range(5):
        label = "TP" if i % 2 == 0 else "FP"
        clf.learn_one({"severity": i, "rule_id_hash": i}, label)
    assert clf.accuracy() is None


# ---------------------------------------------------------------------------
# Stub 4 — accuracy() returns float at or above 10 samples
# ---------------------------------------------------------------------------
@_skip
def test_accuracy_visible_at_10():
    from backend.services.feedback.classifier import FeedbackClassifier
    clf = FeedbackClassifier()
    for i in range(10):
        label = "TP" if i % 2 == 0 else "FP"
        clf.learn_one({"severity": i, "rule_id_hash": i}, label)
    result = clf.accuracy()
    assert isinstance(result, float)


# ---------------------------------------------------------------------------
# Stub 5 — save/load roundtrip preserves n_samples
# ---------------------------------------------------------------------------
@_skip
def test_save_load_roundtrip(tmp_path):
    from backend.services.feedback.classifier import FeedbackClassifier
    clf = FeedbackClassifier(model_dir=tmp_path)
    for i in range(5):
        clf.learn_one({"severity": i, "rule_id_hash": i}, "TP")
    clf.save()

    clf2 = FeedbackClassifier(model_dir=tmp_path)
    clf2.load()
    assert clf2.n_samples == 5


# ---------------------------------------------------------------------------
# Stub 6 — predict_proba_tp returns float in [0.0, 1.0]
# ---------------------------------------------------------------------------
@_skip
def test_predict_proba_tp():
    from backend.services.feedback.classifier import FeedbackClassifier
    clf = FeedbackClassifier()
    result = clf.predict_proba_tp({"severity": 3, "rule_id_hash": 1})
    assert isinstance(result, float)
    assert 0.0 <= result <= 1.0
