from sqlalchemy.dialects.postgresql import ARRAY, TEXT
from sqlalchemy.types import TypeDecorator


class SA_TYPE_TEXT_ARRAY(TypeDecorator):
    """
    Custom SQLAlchemy type for an array of text.
    This is necessary for PostgreSQL to handle lists of strings correctly.
    """

    impl = ARRAY(TEXT)
    cache_ok = True
