"""Tests for Logger."""

import logging
import pytest
from types import SimpleNamespace

from ambdes import Logger


@pytest.mark.unit
def test_log_to_console(caplog):
    """Confirm that logger.log() prints the provided message to the console."""
    # Set up Logger with log_to_console=True
    config = SimpleNamespace(
        log_to_console=True,
        log_to_file=False,
        log_file_path=None
    )
    logger = Logger(config=config)
    # Add message to log
    with caplog.at_level(logging.INFO, logger=logger.logger.name):
        logger.log(sim_time=None, msg="Test console log")
    # Confirm message is in log messages
    assert "Test console log" in caplog.messages


@pytest.mark.unit
def test_log_to_file(tmp_path):
    """
    Confirm that logger.log() would output the message to a .log file at the
    provided file path.
    """
    # Set up logger with log_to_file=True and a temporary log file
    log_path = tmp_path / "test.log"
    config = SimpleNamespace(
        log_to_console=False,
        log_to_file=True,
        log_file_path=log_path
    )
    logger = Logger(config=config)
    # Add message to file
    logger.log(msg="Log message", sim_time=None)
    # Confirm file exists and message is within file
    assert log_path.exists()
    assert "Log message" in log_path.read_text(encoding="utf-8")


@pytest.mark.unit
def test_simtime(caplog):
    """
    Confirm that sim_time is formatted to 3 decimal places and prefixed
    to the log message.
    """
    config = SimpleNamespace(
        log_to_console=True,
        log_to_file=False,
        log_file_path=None
    )
    logger = Logger(config=config)
    with caplog.at_level(logging.INFO, logger=logger.logger.name):
        logger.log(msg="Patient arrives", sim_time=12.3456)
    assert "12.346: Patient arrives" in caplog.messages


@pytest.mark.unit
def test_config_missing_items():
    """
    """
    config = SimpleNamespace(x=1)
    with pytest.raises(AttributeError):
        Logger(config=config)


@pytest.mark.unit
def test_invalid_path():
    """
    Ensure there is appropriate error handling for an invalid file path.
    """
    config = SimpleNamespace(
        log_to_console=False,
        log_to_file=True,
        log_file_path="/invalid/path/to/log.log"
    )
    with pytest.raises(ValueError):
        Logger(config=config)


@pytest.mark.unit
def test_invalid_file_extension():
    """
    Ensure there is appropriate error handling for an invalid file extension.
    """
    config = SimpleNamespace(
        log_to_console=False,
        log_to_file=True,
        log_file_path="test.txt"
    )
    with pytest.raises(ValueError):
        Logger(config=config)
