"""Provider discovery and connection checks used by Settings and Diagnostics."""

from __future__ import annotations

import time
import ipaddress
from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit

from google import genai
from ollama import Client as OllamaClient
from openai import OpenAI

from secure_storage import redact_text, unprotect_secret


GEMINI = "Gemini (Recommended)"
OPENAI_COMPATIBLE = "OpenAI Compatible (For Experts)"
OLLAMA = "Ollama (For Experts)"


@dataclass
class ProviderProbeResult:
    ok: bool
    provider_name: str
    message: str
    latency_ms: int = 0
    models: list[str] = field(default_factory=list)
    configured_model: str = ""
    configured_model_found: bool | None = None
    normalized_values: dict = field(default_factory=dict)


def normalize_base_url(provider_name: str, value: str) -> str:
    """Trim invisible whitespace and repair common Groq/OpenAI URL mistakes."""
    raw = "".join(str(value or "").split()).rstrip("/")
    if not raw:
        return raw
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return raw
    host = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    if provider_name == OPENAI_COMPATIBLE:
        if host == "api.groq.com" and path in ("", "/openai", "/v1"):
            path = "/openai/v1"
        elif host == "api.openai.com" and path in ("", "/"):
            path = "/v1"
    return urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, ""))


def validate_base_url(provider_name: str, value: str) -> str:
    """Reject credential-bearing or insecure remote provider endpoints."""
    normalized = normalize_base_url(provider_name, value)
    try:
        parsed = urlsplit(normalized)
    except ValueError as error:
        raise ValueError("API 地址格式无效") from error
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("API 地址必须是完整的 http:// 或 https:// 地址")
    try:
        parsed.port
    except ValueError as error:
        raise ValueError("API 地址的端口无效") from error
    if parsed.username or parsed.password:
        raise ValueError("API 地址不能包含用户名或密码")
    if parsed.query or parsed.fragment:
        raise ValueError("API 基础地址不能包含查询参数或片段")
    if provider_name == OPENAI_COMPATIBLE and parsed.scheme != "https":
        hostname = parsed.hostname.strip("[]").lower()
        is_loopback = hostname == "localhost"
        try:
            is_loopback = is_loopback or ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            pass
        if not is_loopback:
            raise ValueError("带 API 密钥的远程 OpenAI 兼容接口必须使用 HTTPS")
    return normalized


def _model_name(values: dict, provider_name: str) -> str:
    key = "model_name" if provider_name == GEMINI else "api_model"
    return str(values.get(key, "") or "").strip()


def _safe_error(error: Exception, values: dict) -> str:
    secrets = []
    raw_key = str(values.get("api_key", "") or "")
    if raw_key:
        try:
            secrets.append(unprotect_secret(raw_key))
        except Exception:
            secrets.append(raw_key)
    return redact_text(str(error), secrets)[:600]


def probe_provider(provider_name: str, values: dict) -> ProviderProbeResult:
    """List models and validate that the configured model is available."""
    values = dict(values or {})
    configured_model = _model_name(values, provider_name)
    started = time.perf_counter()
    try:
        if "api_base" in values:
            values["api_base"] = validate_base_url(provider_name, values["api_base"])
        if provider_name == GEMINI:
            api_key = unprotect_secret(values.get("api_key", ""))
            if not api_key:
                raise ValueError("API 密钥不能为空")
            client = genai.Client(api_key=api_key)
            models = sorted({
                str(getattr(model, "name", "")).removeprefix("models/")
                for model in client.models.list()
                if getattr(model, "name", None)
            })
        elif provider_name == OPENAI_COMPATIBLE:
            api_key = unprotect_secret(values.get("api_key", ""))
            base_url = values.get("api_base", "")
            if not api_key:
                raise ValueError("API 密钥不能为空")
            if not base_url:
                raise ValueError("API 基础地址不能为空")
            client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                organization=values.get("api_organisation") or None,
                project=values.get("api_project") or None,
            )
            models = sorted({str(model.id) for model in client.models.list().data if model.id})
        elif provider_name == OLLAMA:
            base_url = values.get("api_base", "")
            if not base_url:
                raise ValueError("Ollama 地址不能为空")
            response = OllamaClient(host=base_url).list()
            raw_models = response.get("models", []) if isinstance(response, dict) else response.models
            models = sorted({
                str(model.get("model") or model.get("name"))
                if isinstance(model, dict)
                else str(getattr(model, "model", None) or getattr(model, "name", ""))
                for model in raw_models
            } - {""})
        else:
            raise ValueError(f"不支持的服务：{provider_name}")

        latency_ms = int((time.perf_counter() - started) * 1000)
        found = configured_model in models if configured_model else None
        if configured_model and not found:
            message = f"连接成功，但当前模型“{configured_model}”未出现在服务返回的模型列表中。"
        else:
            message = f"连接成功，发现 {len(models)} 个模型。"
        return ProviderProbeResult(
            ok=True,
            provider_name=provider_name,
            message=message,
            latency_ms=latency_ms,
            models=models,
            configured_model=configured_model,
            configured_model_found=found,
            normalized_values=values,
        )
    except Exception as error:
        return ProviderProbeResult(
            ok=False,
            provider_name=provider_name,
            message=_safe_error(error, values),
            latency_ms=int((time.perf_counter() - started) * 1000),
            configured_model=configured_model,
            normalized_values=values,
        )
