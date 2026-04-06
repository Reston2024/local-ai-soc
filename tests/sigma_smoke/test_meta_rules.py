"""Sigma smoke tests for meta-detection rules."""
import pytest
from pathlib import Path
from sigma.collection import SigmaCollection

META_DIR = Path(__file__).parent.parent.parent / "detections" / "sigma" / "meta"


@pytest.mark.parametrize("rule_file", list(META_DIR.glob("*.yml")))
def test_meta_detection_rules_parse(rule_file: Path):
    """All meta-detection rules must parse without error."""
    yaml_text = rule_file.read_text(encoding="utf-8")
    collection = SigmaCollection.from_yaml(yaml_text)
    assert len(collection) >= 1, f"Rule {rule_file.name} produced no Sigma rules"
