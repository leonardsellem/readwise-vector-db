import json
from typing import Any, cast

from sqlalchemy import exc
from sqlalchemy.dialects.postgresql import ARRAY, TEXT
from sqlalchemy.types import VARCHAR, TypeDecorator


class SA_TYPE_TEXT_ARRAY(TypeDecorator[list[str]]):  # type: ignore
    """
    Custom SQLAlchemy type for an array of text.
    This is necessary for PostgreSQL to handle lists of strings correctly.
    """

    impl = ARRAY(TEXT)
    cache_ok = True


class JSONEncodedDict(TypeDecorator[dict[str, Any]]):  # type: ignore
    """Represents an immutable structure as a json-encoded string.

    Usage:
        JSONEncodedDict(255)
    """

    impl = VARCHAR

    def process_bind_param(
        self, value: dict[str, Any] | None, dialect: object
    ) -> str | None:
        if value is not None:
            return json.dumps(value)
        return None

    def process_result_value(
        self, value: str | None, dialect: object
    ) -> dict[str, Any] | None:
        if value is not None:
            try:
                return cast(dict[str, Any], json.loads(value))
            except (json.JSONDecodeError, TypeError) as e:
                raise exc.SQLAlchemyError("Failed to decode JSON") from e
        return None
