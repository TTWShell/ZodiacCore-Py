import sys
from typing import Optional, Dict, Any

from loguru import logger
from pydantic import BaseModel, ConfigDict

from zodiac_core.context import get_request_id


class LogFileOptions(BaseModel):
    """
    Configuration options for file logging.

    Allows arbitrary extra arguments to be passed to loguru.add() via extra="allow".
    """

    rotation: str = "10 MB"
    retention: str = "1 week"
    compression: str = "zip"
    enqueue: bool = False
    encoding: str = "utf-8"

    model_config = ConfigDict(extra="allow")


def setup_loguru(
    level: str = "INFO",
    json_format: bool = True,
    service_name: str = "service",
    log_file: Optional[str] = None,
    console_options: Optional[Dict[str, Any]] = None,
    file_options: Optional[LogFileOptions] = None,
):
    """
    Configure Loguru with automatic Trace ID injection and multi-destination output.

    Args:
        level: Logging level (INFO, DEBUG, etc.)
        json_format: Whether to output JSON (True) or Text (False).
        service_name: Name of the service (added to JSON logs).
        log_file: Optional file path to save logs.
        console_options: Extra kwargs to pass to the console sink (e.g. {"enqueue": True}).
        file_options: Configuration model (LogFileOptions) for file sink.
    """
    # 1. Remove default handlers
    logger.remove()

    service = service_name

    # 2. Configure Patcher (Trace ID injection)
    def patcher(record):
        request_id = get_request_id()
        if request_id:
            record["extra"]["request_id"] = request_id
        record["extra"]["service"] = service

    logger.configure(patcher=patcher)

    # 3. Define Formatters
    def _dev_formatter(record):
        if "request_id" not in record["extra"]:
            record["extra"]["request_id"] = "-"
        return (
            "<green>{time:YYYYMMDD HH:mm:ss}</green> "
            "| {extra[service]} "
            "| {extra[request_id]} "
            "| {process.name} "
            "| {thread.name} "
            "| <cyan>{module}</cyan>.<cyan>{function}</cyan> "
            "| <level>{level}</level>: "
            "<level>{message}</level> "
            "| {file.path}:{line}\n"
        )

    # 4. Prepare Console Config
    c_config = console_options or {}
    c_config.setdefault("level", level)
    c_config.setdefault("sink", sys.stderr)

    if json_format:
        c_config.setdefault("serialize", True)
    else:
        c_config.setdefault("format", _dev_formatter)

    # Add Console Sink
    logger.add(**c_config)

    # 5. Prepare File Config (if enabled)
    if log_file:
        if file_options is None:
            file_options = LogFileOptions()
        f_config = file_options.model_dump()

        # Ensure mandatory defaults
        f_config.setdefault("sink", log_file)
        f_config.setdefault("level", level)

        if json_format:
            f_config.setdefault("serialize", True)
        else:
            f_config.setdefault("format", _dev_formatter)

        # Add File Sink
        logger.add(**f_config)
