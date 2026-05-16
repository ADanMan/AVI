import os
import sys


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

import pandas as pd

from src.services.indexing_service import IndexingService


def test_validate_links_csv():
    service = IndexingService()
    df = pd.DataFrame({"rule_id": ["r1", "r2", "r1"], "document_id": ["d1", "d2", "d1"]})
    errors = service.validate_links_csv(df)
    assert any("Duplicate" in e for e in errors)

    df2 = pd.DataFrame({"rule_id": ["r1"], "document_id": ["d1"]})
    errors2 = service.validate_links_csv(df2)
    assert errors2 == []


def test_validate_documents_csv():
    service = IndexingService()
    df = pd.DataFrame({"id": ["d1", "d1"], "text": ["a", "b"]})
    errors = service.validate_documents_csv(df)
    assert any("Duplicate" in e for e in errors)

    df2 = pd.DataFrame({"id": ["d1"], "text": ["a"]})
    errors2 = service.validate_documents_csv(df2)
    assert errors2 == []


def test_validate_rules_csv():
    service = IndexingService()
    df = pd.DataFrame({"id": ["r1", "r1"], "text": ["a", "b"], "risk_level": [1, 2]})
    errors = service.validate_rules_csv(df)
    assert any("Duplicate" in e for e in errors)

    df2 = pd.DataFrame({"id": ["r1"], "text": ["a"], "risk_level": [1]})
    errors2 = service.validate_rules_csv(df2)
    assert errors2 == []
