"""
Cliente HTTP para xAI Grok.
Usa /v1/chat/completions (OpenAI-compatible). Respeta XAI_API_KEY, XAI_MODEL y XAI_BASE_URL desde .env.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import requests

log = logging.getLogger(__name__)

DEFAULT_BASE = "https://api.x.ai"
DEFAULT_MODEL = "grok-4-1-fast-reasoning"


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
        repo_root = Path(__file__).resolve().parents[2]
        # Cargar .env de la raíz (override=True para que tome precedencia)
        for p in (repo_root / ".env", repo_root / "backend" / ".env"):
            if p.exists():
                load_dotenv(p, override=True)
                break
        else:
            load_dotenv()
    except ImportError:
        pass


class XAIError(Exception):
    """Error en llamadas a la API xAI."""

    pass


def _get_api_key() -> str:
    _load_dotenv()
    key = os.environ.get("XAI_API_KEY", "").strip()
    if not key:
        raise XAIError(
            "XAI_API_KEY no está definida. Definila en el entorno o en un .env en la raíz del proyecto."
        )
    if len(key) >= 2 and key[0] == key[-1] and key[0] in ('"', "'"):
        key = key[1:-1].strip()
    return key


def _get_endpoint() -> str:
    base = (os.environ.get("XAI_BASE_URL") or "").strip() or DEFAULT_BASE
    return f"{base.rstrip('/')}/v1/chat/completions"


def _debug_400(
    endpoint: str,
    model: str,
    payload: dict[str, Any],
    resp: Any,
    body: str,
) -> None:
    """Imprime detalles de diagnóstico para HTTP 400 (XAI_DEBUG=1)."""
    import sys
    msg_len = sum(len(str(m.get("content", ""))) for m in payload.get("messages", []))
    sys.stderr.write(
        f"\n[xAI DEBUG 400] endpoint={endpoint} model={model} "
        f"messages_chars={msg_len} status={getattr(resp, 'status_code', '?')}\n"
    )
    sys.stderr.write(f"[xAI DEBUG 400] response_body={repr(body[:2000])}\n")
    # Si body vacío, intentar resp.content y mostrar headers
    if not body and resp is not None:
        raw = getattr(resp, "content", b"")
        if raw:
            sys.stderr.write(f"[xAI DEBUG 400] response_content={raw[:500]!r}\n")
        hdrs = dict(getattr(resp, "headers", {}) or {})
        for k in ("x-request-id", "x-error", "content-type", "x-amzn-errortype"):
            if k in hdrs or k.replace("-", "_") in str(hdrs).lower():
                for hk, hv in hdrs.items():
                    if k in hk.lower():
                        sys.stderr.write(f"[xAI DEBUG 400] header {hk}={hv}\n")
    try:
        if body:
            data = json.loads(body)
            sys.stderr.write(f"[xAI DEBUG 400] parsed_error={json.dumps(data, ensure_ascii=False)[:1000]}\n")
    except Exception:
        pass
    sys.stderr.write("\n")


def _build_response_format(response_format: Any) -> dict[str, Any] | None:
    """Convierte un Pydantic BaseModel class a response_format dict para la API xAI.

    Si response_format es None, retorna None (sin cambios).
    Si es un BaseModel class, genera {"type": "json_schema", "json_schema": {"name": ..., "schema": ...}}.
    Si es un dict, lo pasa tal cual.
    """
    if response_format is None:
        return None
    if isinstance(response_format, dict):
        return response_format
    # Pydantic BaseModel class
    try:
        from pydantic import BaseModel
        if isinstance(response_format, type) and issubclass(response_format, BaseModel):
            schema = response_format.model_json_schema()
            return {
                "type": "json_schema",
                "json_schema": {
                    "name": response_format.__name__,
                    "schema": schema,
                },
            }
    except ImportError:
        pass
    return None


def chat_completion(
    messages: list[dict[str, Any]],
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.3,
    timeout: int | tuple[int, int] = 120,
    response_format: Any | None = None,
) -> str:
    """
    Envía una solicitud de chat completion a xAI Grok.
    Usa XAI_MODEL y XAI_BASE_URL de .env si están definidos.

    Args:
        messages: Lista de mensajes [{"role": "system"|"user"|"assistant", "content": "..."}]
        model: Modelo (p. ej. grok-2). Si XAI_MODEL está en .env, tiene prioridad.
        temperature: Temperatura para la generación.
        timeout: Segundos (int) o (connect, read). Default 120. Para cargas grandes (p. ej. revisiones) usar 180–300.
        response_format: Pydantic BaseModel class, dict, o None. Si se provee, se envía como
            response_format al API para forzar JSON Schema en la respuesta. Si la API lo rechaza
            (400), se reintenta sin él (fallback graceful).

    Returns:
        Contenido del primer choice (content) de la respuesta.

    Raises:
        XAIError: Si falta XAI_API_KEY, timeout, la API devuelve error o falla la conexión.
    """
    _load_dotenv()
    model = (os.environ.get("XAI_MODEL") or "").strip() or model
    api_key = _get_api_key()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    rf = _build_response_format(response_format)
    if rf is not None:
        payload["response_format"] = rf
    endpoint = _get_endpoint()

    try:
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        r = getattr(e, "response", None)
        status = getattr(r, "status_code", None) if r is not None else None
        body = (r.text or "") if r else ""
        body_short = body[:1500] if body else (str(getattr(r, "reason", None)) or "No response body")

        # Fallback: si la API rechaza response_format con 400, reintentar sin él
        if status == 400 and rf is not None:
            body_lower = body.lower()
            if "response_format" in body_lower or "json_schema" in body_lower or "unsupported" in body_lower:
                log.warning("xAI API rechazó response_format — reintentando sin structured outputs (fallback legacy)")
                payload.pop("response_format", None)
                try:
                    resp = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
                    resp.raise_for_status()
                    return _parse_chat_response(resp)
                except requests.exceptions.RequestException:
                    pass  # Caer al manejo de error original

        # Debug 400: imprimir detalles para diagnosticar
        if status == 400 and r is not None and os.environ.get("XAI_DEBUG", "").strip().lower() in ("1", "true", "yes"):
            _debug_400(endpoint, model, payload, r, body)

        err_msg = f"xAI API HTTP {status or '?'}: {body_short}"

        if body and status in (400, 401, 403):
            try:
                data = json.loads(body)
                api_err = (data.get("error") or data.get("message") or "").lower()
                if "incorrect api key" in api_err or ("invalid" in api_err and "key" in api_err):
                    err_msg = (
                        "La API key de xAI no es válida o fue rechazada. "
                        "Obtené una nueva en https://console.x.ai y configurá XAI_API_KEY "
                        "en .env (sin espacios extra ni comillas alrededor del valor)."
                    )
            except Exception:
                pass
        elif status == 404:
            err_msg = (
                "xAI devolvió 404 en /v1/chat/completions. Ese endpoint (legacy) puede estar restringido o no disponible para tu cuenta. "
                "Probá: 1) XAI_MODEL=grok-4 o grok-4-latest en .env (el cliente ya usa XAI_MODEL si está definido). "
                "2) XAI_BASE_URL=https://us-east-1.api.x.ai por si hace falta un endpoint regional. "
                "Revisá https://docs.x.ai y https://console.x.ai/team/default/models."
            )
        raise XAIError(err_msg) from e
    except requests.exceptions.Timeout as e:
        raise XAIError(
            f"Timeout de xAI (lectura/respuesta). Aumentá timeout o revisá conectividad. Detalle: {e}"
        ) from e
    except requests.exceptions.ConnectionError as e:
        raise XAIError(
            f"Error de conexión a xAI. Revisá red, firewall o API. Detalle: {e}"
        ) from e
    except requests.exceptions.RequestException as e:
        raise XAIError(f"xAI API request failed: {e}") from e

    return _parse_chat_response(resp)


def _parse_chat_response_data(data: dict[str, Any]) -> str:
    """Extrae content del primer choice de un response JSON dict. Compartido entre sync y async."""
    choices = data.get("choices") or []
    if not choices:
        raise XAIError("xAI API devolvió choices vacío")
    content = choices[0].get("message", {}).get("content")
    if content is None:
        raise XAIError("xAI API no devolvió content en el message")
    return str(content).strip()


def _parse_chat_response(resp: requests.Response) -> str:
    return _parse_chat_response_data(resp.json())


def chat_completion_with_retry(
    messages: list[dict[str, Any]],
    *,
    retries: int = 3,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.3,
    timeout: int | tuple[int, int] = 120,
    response_format: Any | None = None,
) -> str:
    """
    Igual que chat_completion pero con retry ante 429, 5xx, Timeout y ConnectionError:
    hasta `retries` reintentos (p. ej. 3 → 4 intentos) con exponential backoff.
    Usa XAI_MODEL de .env si está definido; por defecto grok-4-1-fast-reasoning.

    Args:
        response_format: Pydantic BaseModel class, dict, o None. Se pasa a chat_completion
            para forzar JSON Schema en la respuesta. Fallback automático si la API lo rechaza.
    """
    import time

    for attempt in range(retries + 1):
        try:
            return chat_completion(
                messages, model=model, temperature=temperature,
                timeout=timeout, response_format=response_format,
            )
        except XAIError as e:
            cause = getattr(e, "__cause__", None)
            retryable = False

            # 429 o 5xx
            resp = getattr(cause, "response", None) if cause is not None else None
            sc = getattr(resp, "status_code", None) if resp is not None else None
            if sc in (429,) or (sc is not None and 500 <= sc < 600):
                retryable = True

            # Timeout o ConnectionError
            if cause is not None and isinstance(
                cause,
                (
                    requests.exceptions.Timeout,
                    requests.exceptions.ConnectionError,
                ),
            ):
                retryable = True

            if retryable and attempt < retries:
                wait = 2 ** min(attempt, 5)
                time.sleep(wait)
                continue
            raise


# Modelo de imagen por defecto (docs: grok-imagine-image; también grok-2-image-1212 según versión)
DEFAULT_IMAGE_MODEL = "grok-imagine-image"


def _venv_python() -> Path | None:
    """Ruta al Python del .venv del proyecto, o None si no existe."""
    repo_root = Path(__file__).resolve().parents[2]
    for name in ("python", "python3", "python3.11", "python3.10", "python3.12"):
        exe = repo_root / ".venv" / "bin" / name
        if exe.exists():
            return exe
    return None


def _generate_image_via_subprocess(
    prompt: str,
    api_key: str,
    model: str,
    image_format: str,
    aspect_ratio: str | None = None,
) -> str:
    """Genera la imagen ejecutando el Python del .venv en un subprocess (fallback si el import in-process falla)."""
    venv_py = _venv_python()
    if not venv_py:
        raise XAIError("No se encontró .venv/bin/python en el proyecto. Creá el venv en la raíz del repo.")
    script = """
import os, sys
with open(sys.argv[1], "r", encoding="utf-8") as f:
    prompt = f.read()
from xai_sdk import Client
kwargs = {"prompt": prompt, "model": os.environ.get("XAI_IMAGE_MODEL") or "grok-imagine-image", "image_format": os.environ.get("XAI_IMAGE_FORMAT") or "url"}
if os.environ.get("XAI_IMAGE_ASPECT_RATIO"):
    kwargs["aspect_ratio"] = os.environ.get("XAI_IMAGE_ASPECT_RATIO")
r = Client(api_key=os.environ["XAI_API_KEY"]).image.sample(**kwargs)
print(getattr(r, "url", "") or "")
"""
    env = {**os.environ, "XAI_API_KEY": api_key, "XAI_IMAGE_MODEL": model, "XAI_IMAGE_FORMAT": image_format}
    if aspect_ratio:
        env["XAI_IMAGE_ASPECT_RATIO"] = aspect_ratio
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(prompt)
        tmp = f.name
    try:
        out = subprocess.run(
            [str(venv_py), "-c", script, tmp],
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=Path(__file__).resolve().parents[2],
        )
        if out.returncode != 0:
            raise XAIError(f"Subprocess xAI imagen: {out.stderr or out.stdout or 'error desconocido'}")
        url = (out.stdout or "").strip()
        if not url:
            raise XAIError("El subprocess no devolvió URL de imagen.")
        return url
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def generate_image_vertex(
    prompt: str,
    *,
    aspect_ratio: str = "16:9",
) -> str:
    """
    Genera una imagen con Vertex AI (Gemini / Nano Banana).
    Usa GOOGLE_GENAI_USE_VERTEXAI=True, GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION
    (y opcional GOOGLE_CLOUD_API_KEY). Devuelve data URL (data:image/png;base64,...).
    """
    import base64 as _base64

    _load_dotenv()
    try:
        from google import genai
        from google.genai import types
    except ImportError as e:
        raise XAIError("Para Vertex imagen hace falta: pip install google-genai") from e
    api_key = (os.environ.get("GOOGLE_CLOUD_API_KEY") or "").strip() or None
    client = genai.Client(vertexai=True, api_key=api_key) if api_key else genai.Client(vertexai=True)
    model = (os.environ.get("VERTEX_IMAGE_MODEL") or "").strip() or "gemini-2.5-flash-image"
    contents = [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])]
    config = types.GenerateContentConfig(
        temperature=1,
        top_p=0.95,
        max_output_tokens=32768,
        response_modalities=["TEXT", "IMAGE"],
        safety_settings=[
            types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
            types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
        ],
        image_config=types.ImageConfig(
            aspect_ratio=aspect_ratio or "16:9",
            image_size="1K",
            output_mime_type="image/png",
        ),
    )
    try:
        response = client.models.generate_content(model=model, contents=contents, config=config)
    except Exception as e:
        raise XAIError(f"Vertex imagen falló: {e}") from e
    if not response.candidates or not response.candidates[0].content.parts:
        raise XAIError("Vertex no devolvió imagen en la respuesta.")
    for part in response.candidates[0].content.parts:
        if getattr(part, "inline_data", None) and getattr(part.inline_data, "data", None):
            b64 = _base64.b64encode(part.inline_data.data).decode("ascii")
            return f"data:image/png;base64,{b64}"
    raise XAIError("Vertex no devolvió datos de imagen (inline_data) en la respuesta.")


def generate_image(
    prompt: str,
    *,
    image_format: str = "url",
    model: str | None = None,
    aspect_ratio: str | None = None,
) -> str:
    """
    Genera una imagen desde un prompt. Si IMAGE_PROVIDER=vertex usa Vertex (Gemini/Nano Banana);
    si no, usa xAI (grok-imagine-image).
    """
    _load_dotenv()
    provider = (os.environ.get("IMAGE_PROVIDER") or "").strip().lower()
    if provider == "vertex":
        return generate_image_vertex(prompt, aspect_ratio=aspect_ratio or "16:9")

    """
    xAI: Requiere xai_sdk y XAI_API_KEY. Si el import falla, usa subprocess con .venv.
    """
    import logging
    log = logging.getLogger(__name__)
    log.warning("generate_image() llamado (fallback subprocess si import falla)")
    api_key = _get_api_key()
    model = (os.environ.get("XAI_IMAGE_MODEL") or "").strip() or model or DEFAULT_IMAGE_MODEL

    try:
        from xai_sdk import Client
    except ImportError:
        log.warning("xai_sdk no en proceso -> usando subprocess con .venv")
        return _generate_image_via_subprocess(prompt, api_key, model, image_format, aspect_ratio)

    client = Client(api_key=api_key)
    # Llamar con prompt y model posicionales como en la doc; aspect_ratio obligatorio para prototipos horizontales
    try:
        if aspect_ratio:
            response = client.image.sample(prompt, model, image_format=image_format, aspect_ratio=aspect_ratio)
        else:
            response = client.image.sample(prompt, model, image_format=image_format)
    except Exception as e:
        raise XAIError(f"Generación de imagen falló: {e}") from e
    if image_format == "base64":
        return getattr(response, "image", None) or ""
    return getattr(response, "url", None) or ""
