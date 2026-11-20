"""Shared pieces for the research setups, which answer the funding question with structured output."""
from __future__ import annotations

from typing import Any

from .. import http_client
from ..http_client import Response
from ..tool_base import Adapter

# Research requests run long and are retried on 429, 5xx and dropped connections, like the runs on the board.
TIMEOUT = 180.0
ATTEMPTS = 4


class HttpError(RuntimeError):
    def __init__(self, response: Response) -> None:
        super().__init__(f"HTTP {response.status}: {str(response.body)[:300]}")
        self.response = response


class ResearchAdapter(Adapter):
    def call(self, method: str, url: str, headers: dict[str, str], payload: Any = None, *,
             timeout: float | None = None, attempts: int = ATTEMPTS, ok_statuses: frozenset[int] = frozenset()) -> Response:
        """Send one request and raise HttpError for a non-2xx status that is not in `ok_statuses`."""
        response = http_client.request(method, url, headers=headers, json=payload,
                                       timeout=timeout or float(self.settings.get("timeout_seconds") or TIMEOUT),
                                       attempts=attempts)
        if not response.ok and response.status not in ok_statuses:
            raise HttpError(response)
        return response
