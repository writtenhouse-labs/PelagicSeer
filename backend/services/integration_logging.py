import logging
import time
from typing import Any


logger = logging.getLogger("pelagicseer.integrations")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
logger.propagate = False


def _format_fields(fields: dict[str, Any]) -> str:
    parts = []
    for key, value in fields.items():
        if value is None:
            continue
        text = str(value).replace("\n", " ").replace("\r", " ")
        if len(text) > 220:
            text = f"{text[:217]}..."
        parts.append(f"{key}={text}")
    return " ".join(parts)


class IntegrationSpan:
    def __init__(self, source: str, operation: str, **metadata: Any) -> None:
        self.source = source
        self.operation = operation
        self.metadata = metadata
        self.started = time.perf_counter()
        self.metrics: dict[str, Any] = {}

    def __enter__(self) -> "IntegrationSpan":
        logger.info(
            "integration.start %s",
            _format_fields(
                {
                    "source": self.source,
                    "operation": self.operation,
                    **self.metadata,
                }
            ),
        )
        return self

    def add(self, **metrics: Any) -> None:
        self.metrics.update(metrics)

    def __exit__(self, exc_type, exc, traceback) -> bool:
        elapsed_ms = round((time.perf_counter() - self.started) * 1000, 1)
        fields = {
            "source": self.source,
            "operation": self.operation,
            "elapsed_ms": elapsed_ms,
            "connection_closed": True,
            **self.metadata,
            **self.metrics,
        }
        if exc is None:
            logger.info("integration.success %s", _format_fields(fields))
        else:
            logger.warning(
                "integration.failure %s",
                _format_fields(
                    {
                        **fields,
                        "error_type": exc.__class__.__name__,
                        "error": exc,
                    }
                ),
            )
        return False


def integration_span(source: str, operation: str, **metadata: Any) -> IntegrationSpan:
    return IntegrationSpan(source, operation, **metadata)
