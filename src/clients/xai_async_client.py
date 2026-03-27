"""
Cliente HTTP async para xAI Grok.
Usa httpx.AsyncClient con connection pooling para alto rendimiento concurrente.
Reutiliza la misma lógica de error handling, response_format y fallback del cliente sync.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import httpx

log = logging.getLogger(__name__)

# Reutilizar constantes y helpers del cliente sync
from src.clients.xai_client import (
    DEFAULT_BASE,
    DEFAULT_MODEL,
    XAIError,
    _build_response_format,
    _get_api_key,
    _get_endpoint,
    _load_dotenv,
    _parse_chat_response_data,
)


# ---------------------------------------------------------------------------
# Singleton AsyncClient con connection pooling
# ---------------------------------------------------------------------------

_client: httpx.AsyncClient | None = None
_client_lock = asyncio.Lock()


async def _get_client() -> httpx.AsyncClient:
    """Retorna un AsyncClient singleton con connection pooling."""
    global _client
    if _client is not None and not _client.is_closed:
        return _client

    async with _client_lock:
        # Double-check después del lock
        if _client is not None and not _client.is_closed:
            return _client

        _load_dotenv()
        api_key = _get_api_key()

        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(180.0, connect=10.0),
            limits=httpx.Limits(
                max_connections=30,
                max_keepalive_connections=20,
            ),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        return _client


async def close_client() -> None:
    """Cierra el AsyncClient. Llamar al final del pipeline."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None


# ---------------------------------------------------------------------------
# Async chat completion
# ---------------------------------------------------------------------------

async def async_chat_completion(
    messages: list[dict[str, Any]],
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.3,
    timeout: float = 180.0,
    response_format: Any | None = None,
) -> str:
    """
    Versión async de chat_completion con connection pooling via httpx.

    Args:
        messages: Lista de mensajes [{\"role\": \"system\"|\"user\"|\"assistant\", \"content\": \"...\"}]
        model: Modelo. Si XAI_MODEL está en .env, tiene prioridad.
        temperature: Temperatura para la generación.
        timeout: Timeout en segundos.
        response_format: Pydantic BaseModel class, dict, o None.

    Returns:
        Contenido del primer choice (content) de la respuesta.
    """
    _load_dotenv()
    model = (os.environ.get("XAI_MODEL") or "").strip() or model
    endpoint = _get_endpoint()

    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    rf = _build_response_format(response_format)
    if rf is not None:
        payload["response_format"] = rf

    client = await _get_client()

    try:
        resp = await client.post(
            endpoint,
            json=payload,
            timeout=timeout,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        body = e.response.text or ""
        body_short = body[:1500] if body else "No response body"

        # Fallback: si la API rechaza response_format con 400, reintentar sin él
        if status == 400 and rf is not None:
            body_lower = body.lower()
            if "response_format" in body_lower or "json_schema" in body_lower or "unsupported" in body_lower:
                log.warning("xAI API rechazó response_format — reintentando sin structured outputs (fallback legacy)")
                payload.pop("response_format", None)
                try:
                    resp = await client.post(endpoint, json=payload, timeout=timeout)
                    resp.raise_for_status()
                    data = resp.json()
                    return _parse_chat_response_data(data)
                except httpx.HTTPError:
                    pass  # Caer al manejo de error original

        err_msg = f"xAI API HTTP {status}: {body_short}"

        if body and status in (400, 401, 403):
            try:
                data = json.loads(body)
                api_err = (data.get("error") or data.get("message") or "").lower()
                if "incorrect api key" in api_err or ("invalid" in api_err and "key" in api_err):
                    err_msg = (
                        "La API key de xAI no es válida o fue rechazada. "
                        "Obtené una nueva en https://console.x.ai y configurá XAI_API_KEY."
                    )
            except Exception:
                pass
        raise XAIError(err_msg) from e

    except httpx.TimeoutException as e:
        raise XAIError(f"Timeout de xAI async: {e}") from e
    except httpx.ConnectError as e:
        raise XAIError(f"Error de conexión async a xAI: {e}") from e
    except httpx.HTTPError as e:
        raise XAIError(f"xAI async request failed: {e}") from e

    data = resp.json()
    return _parse_chat_response_data(data)


async def async_chat_completion_with_retry(
    messages: list[dict[str, Any]],
    *,
    retries: int = 3,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.3,
    timeout: float = 180.0,
    response_format: Any | None = None,
) -> str:
    """
    Async chat_completion con retry ante 429, 5xx, Timeout y ConnectionError.
    Exponential backoff: 1s, 2s, 4s, 8s...
    """
    for attempt in range(retries + 1):
        try:
            return await async_chat_completion(
                messages,
                model=model,
                temperature=temperature,
                timeout=timeout,
                response_format=response_format,
            )
        except XAIError as e:
            cause = getattr(e, "__cause__", None)
            retryable = False

            # 429 o 5xx
            if isinstance(cause, httpx.HTTPStatusError):
                sc = cause.response.status_code
                if sc == 429 or 500 <= sc < 600:
                    retryable = True

            # Timeout o ConnectionError
            if isinstance(cause, (httpx.TimeoutException, httpx.ConnectError)):
                retryable = True

            if retryable and attempt < retries:
                wait = 2 ** min(attempt, 5)
                log.info(f"xAI async retry {attempt + 1}/{retries} en {wait}s...")
                await asyncio.sleep(wait)
                continue
            raise
