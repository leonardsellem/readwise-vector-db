import inspect

from readwise_vector_db.models import Highlight, SyncState


def test_model_classes_exist():
    """Ensure essential model classes are importable and recognised as classes."""
    assert inspect.isclass(Highlight)
    assert inspect.isclass(SyncState)
