import os
import tempfile

import pytest
from loguru import logger

from zodiac_core.logging import setup_loguru, LogFileOptions
from zodiac_core.context import set_request_id


@pytest.mark.asyncio
async def test_setup_loguru_file_output():
    with tempfile.TemporaryDirectory() as tmp_dir:
        log_file = os.path.join(tmp_dir, "test.log")

        # 1. Setup loguru with file output (using defaults)
        setup_loguru(
            level="DEBUG",
            json_format=False,
            log_file=log_file,
            service_name="test-service"
        )

        # 2. Log some message
        test_msg = "Test file logging message"
        trace_id = "test-trace-id"
        set_request_id(trace_id)
        logger.info(test_msg)

        # 3. Verify file exists and contains the message
        assert os.path.exists(log_file)
        with open(log_file, "r") as f:
            content = f.read()
            assert test_msg in content
            assert trace_id in content
            assert "test-service" in content


@pytest.mark.asyncio
async def test_setup_loguru_json_file_output_with_options():
    with tempfile.TemporaryDirectory() as tmp_dir:
        log_file = os.path.join(tmp_dir, "test.json.log")

        # 1. Setup loguru with JSON file output and CUSTOM options (Model)
        # We override rotation and add 'enqueue' which wasn't supported before
        options = LogFileOptions(
            rotation="1 KB",
            enqueue=True,  # Async logging
            encoding="utf-8"
        )

        setup_loguru(
            level="DEBUG",
            json_format=True,
            log_file=log_file,
            service_name="json-service",
            file_options=options
        )

        # 2. Log some message
        test_msg = "Test JSON file logging"
        logger.info(test_msg)

        # Force flush/cleanup
        logger.complete()
        logger.remove()

        # 3. Verify file exists and contains JSON
        assert os.path.exists(log_file)
        with open(log_file, "r", encoding="utf-8") as f:
            line = f.readline()
            assert test_msg in line
            assert "json-service" in line


@pytest.mark.asyncio
async def test_setup_loguru_with_pydantic_options():
    with tempfile.TemporaryDirectory() as tmp_dir:
        log_file = os.path.join(tmp_dir, "test_pydantic.log")

        # 1. Create options using Pydantic model
        options = LogFileOptions(
            rotation="5 MB",
            retention="1 day",
            compression="gz",
            # Extra field allowed by ConfigDict
            delay=True
        )

        # 2. Setup
        setup_loguru(
            level="INFO",
            log_file=log_file,
            file_options=options
        )

        logger.info("Pydantic Config Test")
        logger.complete()
        logger.remove()

        assert os.path.exists(log_file)
