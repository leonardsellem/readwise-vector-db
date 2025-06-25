import json
from unittest.mock import patch

from typer.testing import CliRunner

from readwise_vector_db.main import app

runner = CliRunner()


def test_search_command():
    with patch("readwise_vector_db.main.semantic_search") as mock_semantic_search:
        mock_semantic_search.return_value = [
            {
                "id": "123",
                "text": "This is a test highlight.",
                "score": 0.99,
            }
        ]

        result = runner.invoke(app, ["search", "test query"])

        assert result.exit_code == 0
        assert "Searching for: 'test query'..." in result.stdout

        # The output from the command will have a trailing newline
        # so we load the mock result and dump it back to string to match
        expected_json_output = json.dumps(mock_semantic_search.return_value, indent=2)
        assert expected_json_output in result.stdout

        mock_semantic_search.assert_called_once_with("test query", 20)


def test_search_command_with_k():
    with patch("readwise_vector_db.main.semantic_search") as mock_semantic_search:
        mock_semantic_search.return_value = []

        result = runner.invoke(app, ["search", "another query", "--k", "5"])

        assert result.exit_code == 0
        assert "Searching for: 'another query'..." in result.stdout

        # The output is formatted with an indent of 2
        assert json.dumps([], indent=2) in result.stdout

        mock_semantic_search.assert_called_once_with("another query", 5)


def test_sync_backfill():
    with patch("readwise_vector_db.main.run_backfill") as mock_run_backfill:
        result = runner.invoke(app, ["sync", "--backfill"])
        assert result.exit_code == 0
        assert "Starting Readwise backfill sync..." in result.stdout
        mock_run_backfill.assert_called_once()


def test_sync_incremental():
    with patch(
        "readwise_vector_db.main.run_incremental_sync"
    ) as mock_run_incremental_sync:
        result = runner.invoke(app, ["sync", "--since", "2023-01-01"])
        assert result.exit_code == 0
        mock_run_incremental_sync.assert_called_once_with(since="2023-01-01")


def test_sync_mutually_exclusive_options():
    result = runner.invoke(app, ["sync", "--backfill", "--since", "2023-01-01"])
    assert result.exit_code == 1
    assert "Error: --backfill and --since are mutually exclusive." in result.stdout
