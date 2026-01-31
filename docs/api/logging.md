# Logging & Observability

ZodiacCore provides a pre-configured, production-ready logging system based on **Loguru**. It is designed for observability, supporting JSON structured logs and automatic Trace ID correlation.

## 1. Core Concepts

### Structured Logging
By default, ZodiacCore outputs logs in **JSON format**. This is ideal for production environments (e.g., ELK stack, Datadog, CloudWatch) as it makes log parsing and searching significantly easier.

### Trace ID Correlation
Every log message automatically includes a `request_id` if it was generated during an active web request. This allows you to correlate multiple log lines across different services for a single transaction.

---

## 2. Quick Setup

The most common way to initialize logging is in your application's entry point (`main.py`).

```python
from zodiac_core.logging import setup_loguru

setup_loguru(
    level="INFO",
    json_format=True,        # Use JSON for production
    service_name="payment-service"
)
```

---

## 3. Advanced Configuration

### Console & File Output
You can log to both the console and a file simultaneously.

```python
from zodiac_core.logging import setup_loguru, LogFileOptions

setup_loguru(
    level="DEBUG",
    json_format=False,       # Use human-readable text for local dev
    log_file="logs/app.log",
    file_options=LogFileOptions(
        rotation="500 MB",
        retention="10 days",
        compression="zip"
    )
)
```

### Passing Extra Sink Options
The `console_options` argument allows you to pass arbitrary keyword arguments directly to the Loguru `add()` method.

```python
setup_loguru(
    console_options={"enqueue": True, "backtrace": True, "diagnose": True}
)
```

---

## 4. How to Log

Since ZodiacCore configures the standard `loguru.logger`, you can simply import and use it anywhere in your code.

```python
from loguru import logger

def process_data(data):
    logger.info("Processing data", extra={"data_id": data.id})
    # If this runs during a request, 'request_id' is automatically added!
```

---

## 5. JSON Log Structure

A typical JSON log entry produced by ZodiacCore looks like this:

```json
{
  "text": "2026-01-31 17:26:24.208 | INFO     | demo_r:read_item:23 - request: item_id=1\n",
  "record": {
    "elapsed": {
      "repr": "0:00:14.429585",
      "seconds": 14.429585
    },
    "exception": null,
    "extra": {
      "request_id": "98277dc9-27ca-4849-98f0-6097c3b41867",
      "service": "service"
    },
    "file": {
      "name": "demo_r.py",
      "path": "/Users/legolas/workspace/ZodiacCore-Py/demo_r.py"
    },
    "function": "read_item",
    "level": {
      "icon": "ℹ️",
      "name": "INFO",
      "no": 20
    },
    "line": 23,
    "message": "request: item_id=1",
    "module": "demo_r",
    "name": "demo_r",
    "process": {
      "id": 92473,
      "name": "MainProcess"
    },
    "thread": {
      "id": 140704462000000,
      "name": "MainThread"
    },
    "time": {
      "repr": "2026-01-31 17:26:24.208560+08:00",
      "timestamp": 1769851584.20856
    }
  }
}
```

---

## 6. API Reference

### Logging Utilities
::: zodiac_core.logging
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - setup_loguru
        - LogFileOptions