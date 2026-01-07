import sys

from loguru import logger

from zodiac_core.context import get_request_id


def setup_loguru(
    level: str = "INFO",
    json_format: bool = True,
    service_name: str = "service"
):
    """
    Configure Loguru with automatic Trace ID injection and JSON output.

    Args:
        level: Logging level (INFO, DEBUG, etc.)
        json_format: Whether to output JSON (True) or Text (False).
        service_name: Name of the service (added to JSON logs).
    """
    # 1. Remove default handlers to prevent duplicate logs
    logger.remove()

    service = service_name

    # 2. Define the Patcher function
    # This runs for every log record, injecting the current trace_id from context
    def patcher(record):
        request_id = get_request_id()
        if request_id:
            record["extra"]["request_id"] = request_id
        record["extra"]["service"] = service

    # 3. Configure Loguru
    # We use 'configure' to apply the patcher globally
    logger.configure(patcher=patcher)

    # 4. Add the sink (Output destination)
    if json_format:
        # Serialize=True automatically converts the log record (including extra) to JSON
        logger.add(sys.stderr, level=level, serialize=True)
    else:
        # Dev format: Readable text with the request_id visible
        fmt = (
            "<green>{time:YYYYMMDD HH:mm:ss}</green> "
            "| {process.name} "
            "| {thread.name}"
            "| <cyan>{module}</cyan>.<cyan>{function}</cyan>"
            "| <level>{level}</level>: "
            "<level>{message}</level> "
            "| {file.path}:{line} ",  # File path and line number (clickable in VSCode)
        )
        logger.add(sys.stderr, enqueue=True, level=level, format=fmt)
