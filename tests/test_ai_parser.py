"""Dedicated tests for ai_parser.py -- provider routing, failover, and
vision gating.

WHY MOCKED PROVIDERS: ai_parser.py is the external AI-provider
data-exfiltration surface. Every provider client is replaced with a
synthetic fake so no real network call ever happens and no real customer
data, API keys, or credentials are used. All fixtures are synthetic.

These tests exercise the public interfaces:
  - LLMFailoverRouter.generate_response()  (provider ordering / failover)
  - AIParser.parse_text() / parse_image()  (routing + vision gating)
  - _extract_json_array() / _map_common_keys()  (response handling)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import httpx

from ai_parser import (
    AI_PROMPT,
    SYSTEM_PROMPT,
    AIParser,
    LLMFailoverRouter,
    ParserError,
    Provider,
    _extract_json_array,
    _map_common_keys,
)
from config import Settings
from openai import APIError, RateLimitError
from validation import STANDARD_KEYS, ValidationError


def make_rate_limit_error(message: str = "rate limited") -> RateLimitError:
    """Construct a RateLimitError with the httpx args the openai lib requires."""
    return RateLimitError(
        message,
        response=httpx.Response(429, request=httpx.Request("POST", "https://test")),
        body=None,
    )


def make_api_error(message: str = "bad request") -> APIError:
    """Construct an APIError with the httpx args the openai lib requires."""
    return APIError(
        message,
        request=httpx.Request("POST", "https://test"),
        body=None,
    )


# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

def make_settings(**overrides) -> Settings:
    """Build a Settings with dummy values and optional provider-key overrides."""
    defaults = {
        "telegram_bot_token": "x",
        "openai_api_key": "fake-key-for-tests",
    }
    defaults.update(overrides)
    return Settings(**defaults)


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeChoice:
    def __init__(self, content: str):
        self.message = _FakeMessage(content)


class _FakeResponse:
    """Shape matches what ai_parser reads: response.choices[0].message.content."""

    def __init__(self, content: str):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    """Fake for provider.client.chat.completions.create()."""

    def __init__(self, scripted_output, raise_exc=None):
        self._scripted_output = scripted_output
        self._raise_exc = raise_exc
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._raise_exc is not None:
            raise self._raise_exc
        output = self._scripted_output
        if callable(output):
            output = output(kwargs)
        return _FakeResponse(output)


class _FakeChat:
    def __init__(self, completions):
        self.completions = completions


class _FakeClient:
    """Drop-in stand-in for AsyncOpenAI with a scripted chat.completions."""

    def __init__(self, scripted_output, raise_exc=None):
        self.chat = _FakeChat(_FakeCompletions(scripted_output, raise_exc))

    @property
    def completions(self):
        return self.chat.completions


def make_router(providers: list[Provider]) -> LLMFailoverRouter:
    """Build a router with a dummy settings object, then replace its
    providers with the synthetic list passed in."""
    router = LLMFailoverRouter(make_settings())
    router.providers = providers
    return router


def make_provider(name: str, scripted_output, *, supports_vision: bool = True,
                  raise_exc=None) -> Provider:
    return Provider(
        name=name,
        client=_FakeClient(scripted_output, raise_exc),
        model="test-model",
        supports_vision=supports_vision,
    )


# ---------------------------------------------------------------------------
# Provider configuration / ordering
# ---------------------------------------------------------------------------

class TestProviderConfiguration:
    """Provider registration order and vision flags."""

    def test_all_providers_registered_in_order(self):
        settings = make_settings(
            openai_api_key="k",
            gemini_api_key="k",
            github_token="k",
            openrouter_api_key="k",
            groq_api_key="k",
            deepseek_api_key="k",
        )
        router = LLMFailoverRouter(settings)
        names = [p.name for p in router.providers]
        assert names == ["OpenAI", "Gemini", "GitHub", "OpenRouter", "Groq", "DeepSeek"]

    def test_only_groq_registered_when_only_groq_key_set(self):
        settings = make_settings(openai_api_key=None, groq_api_key="k")
        router = LLMFailoverRouter(settings)
        assert [p.name for p in router.providers] == ["Groq"]

    def test_no_providers_when_no_keys(self):
        settings = make_settings(openai_api_key=None)
        router = LLMFailoverRouter(settings)
        assert router.providers == []

    def test_vision_flags(self):
        settings = make_settings(
            openai_api_key="k",
            gemini_api_key="k",
            github_token="k",
            openrouter_api_key="k",
            groq_api_key="k",
            deepseek_api_key="k",
        )
        router = LLMFailoverRouter(settings)
        vision = {p.name: p.supports_vision for p in router.providers}
        assert vision == {
            "OpenAI": True,
            "Gemini": True,
            "GitHub": True,
            "OpenRouter": True,
            "Groq": False,
            "DeepSeek": False,
        }

    @pytest.mark.asyncio
    async def test_no_providers_raises_parser_error(self):
        router = make_router([])
        with pytest.raises(ParserError, match="OPENAI_API_KEY is required"):
            await router.generate_response([{"role": "user", "content": "hi"}])


# ---------------------------------------------------------------------------
# Provider failover
# ---------------------------------------------------------------------------

class TestProviderFailover:
    """Routing and fallback behavior."""

    @pytest.mark.asyncio
    async def test_first_provider_success_returns_content(self):
        router = make_router([
            make_provider("OpenAI", '[{"loan_number":"L1"}]'),
            make_provider("Gemini", "SHOULD NOT BE CALLED"),
        ])
        result = await router.generate_response([{"role": "user", "content": "hi"}])
        assert result == '[{"loan_number":"L1"}]'
        # Second provider's create must never be invoked.
        assert router.providers[1].client.completions.calls == []

    @pytest.mark.asyncio
    async def test_rate_limit_falls_back_to_next(self):
        router = make_router([
            make_provider("OpenAI", "SHOULD NOT BE USED",
                          raise_exc=make_rate_limit_error()),
            make_provider("Gemini", '[{"loan_number":"L2"}]'),
        ])
        result = await router.generate_response([{"role": "user", "content": "hi"}])
        assert result == '[{"loan_number":"L2"}]'

    @pytest.mark.asyncio
    async def test_api_error_falls_back_to_next(self):
        router = make_router([
            make_provider("OpenAI", "SHOULD NOT BE USED",
                          raise_exc=make_api_error()),
            make_provider("Gemini", '[{"loan_number":"L3"}]'),
        ])
        result = await router.generate_response([{"role": "user", "content": "hi"}])
        assert result == '[{"loan_number":"L3"}]'

    @pytest.mark.asyncio
    async def test_generic_exception_falls_back_to_next(self):
        router = make_router([
            make_provider("OpenAI", "SHOULD NOT BE USED", raise_exc=RuntimeError("boom")),
            make_provider("Gemini", '[{"loan_number":"L4"}]'),
        ])
        result = await router.generate_response([{"role": "user", "content": "hi"}])
        assert result == '[{"loan_number":"L4"}]'

    @pytest.mark.asyncio
    async def test_all_providers_fail_raises_parser_error(self):
        router = make_router([
            make_provider("OpenAI", "x", raise_exc=make_rate_limit_error()),
            make_provider("Gemini", "x", raise_exc=make_api_error()),
        ])
        with pytest.raises(ParserError, match="All available AI providers failed"):
            await router.generate_response([{"role": "user", "content": "hi"}])

    @pytest.mark.asyncio
    async def test_vision_required_with_only_text_providers_fails(self):
        router = make_router([
            make_provider("Groq", "x", supports_vision=False),
            make_provider("DeepSeek", "x", supports_vision=False),
        ])
        with pytest.raises(ParserError, match="All Vision-capable AI providers failed"):
            await router.generate_response([{"role": "user", "content": "hi"}], requires_vision=True)

    @pytest.mark.asyncio
    async def test_vision_required_skips_text_only_provider(self):
        text_only = make_provider("Groq", "SHOULD NOT BE CALLED", supports_vision=False)
        vision = make_provider("OpenAI", '[{"loan_number":"L5"}]', supports_vision=True)
        router = make_router([text_only, vision])
        result = await router.generate_response(
            [{"role": "user", "content": "hi"}], requires_vision=True
        )
        assert result == '[{"loan_number":"L5"}]'
        # Text-only provider's create must never be invoked.
        assert text_only.client.completions.calls == []


# ---------------------------------------------------------------------------
# Malformed / unexpected provider responses
# ---------------------------------------------------------------------------

class TestMalformedResponses:
    """Response parsing edge cases."""

    def test_extract_json_array_raises_when_no_array(self):
        with pytest.raises(ParserError, match="did not return a JSON array"):
            _extract_json_array("no brackets here")

    def test_extract_json_array_handles_markdown_fences(self):
        raw = "```json\n[{\"loan_number\":\"L1\"}]\n```"
        assert _extract_json_array(raw) == '[{"loan_number":"L1"}]'

    def test_extract_json_array_handles_leading_text(self):
        raw = "Here is the data: [{\"loan_number\":\"L1\"}]"
        assert _extract_json_array(raw) == '[{"loan_number":"L1"}]'

    @pytest.mark.asyncio
    async def test_malformed_json_from_provider_raises_validation_error(self):
        # generate_response only returns raw text; the JSON validation
        # happens in AIParser.parse_text via load_json_array. The text
        # must contain a [...] array (so _extract_json_array passes) but
        # the JSON inside must be malformed.
        parser = AIParser(make_settings())
        parser.router = make_router([make_provider("OpenAI", "[not valid json]")])
        with pytest.raises(ValidationError, match="Malformed JSON"):
            await parser.parse_text("some free text")

    @pytest.mark.asyncio
    async def test_empty_array_from_provider_raises_validation_error(self):
        # An empty [] array passes _extract_json_array but is rejected by
        # load_json_array as an empty import.
        parser = AIParser(make_settings())
        parser.router = make_router([make_provider("OpenAI", "[]")])
        with pytest.raises(ValidationError, match="Import is empty"):
            await parser.parse_text("some free text")


# ---------------------------------------------------------------------------
# AIParser.parse_text
# ---------------------------------------------------------------------------

class TestParseText:
    """Text parsing: JSON short-circuit vs AI routing."""

    @pytest.mark.asyncio
    async def test_empty_text_raises_parser_error(self):
        parser = AIParser(make_settings())
        with pytest.raises(ParserError, match="No text was provided"):
            await parser.parse_text("   ")

    @pytest.mark.asyncio
    async def test_json_array_short_circuits_without_client_call(self):
        parser = AIParser(make_settings())
        # Replace client with a fake that would fail if called.
        parser.client = _FakeClient("SHOULD NOT BE CALLED")
        result = await parser.parse_text('[{"loan_number":"L1","first_name":"Ann"}]')
        assert result == [{"loan_number": "L1", "first_name": "Ann"}]
        assert parser.client.completions.calls == []

    @pytest.mark.asyncio
    async def test_single_json_object_auto_wrapped(self):
        parser = AIParser(make_settings())
        parser.client = _FakeClient("SHOULD NOT BE CALLED")
        result = await parser.parse_text('{"loan_number":"L1","first_name":"Ann"}')
        assert result == [{"loan_number": "L1", "first_name": "Ann"}]

    @pytest.mark.asyncio
    async def test_free_text_routes_through_router(self):
        parser = AIParser(make_settings())
        # Replace the router with one that has a single fake provider.
        parser.router = make_router([
            make_provider("OpenAI", '[{"loan_number":"L1","first_name":"Ann"}]')
        ])
        result = await parser.parse_text("Ann Owens, loan L1")
        assert result == [{"loan_number": "L1", "first_name": "Ann"}]

    @pytest.mark.asyncio
    async def test_human_readable_keys_mapped(self):
        parser = AIParser(make_settings())
        parser.router = make_router([
            make_provider("OpenAI", '[{"Loan Number":"L1","First Name":"Ann"}]')
        ])
        result = await parser.parse_text("Ann Owens, loan L1")
        assert result == [{"loan_number": "L1", "first_name": "Ann"}]


# ---------------------------------------------------------------------------
# AIParser.parse_image
# ---------------------------------------------------------------------------

class TestParseImage:
    """Image parsing: file validation + vision routing."""

    @pytest.mark.asyncio
    async def test_missing_file_raises_parser_error(self, tmp_path):
        parser = AIParser(make_settings())
        with pytest.raises(ParserError, match="could not be read"):
            await parser.parse_image(tmp_path / "nonexistent.png")

    @pytest.mark.asyncio
    async def test_empty_file_raises_parser_error(self, tmp_path):
        empty = tmp_path / "empty.png"
        empty.write_bytes(b"")
        parser = AIParser(make_settings())
        with pytest.raises(ParserError, match="could not be read"):
            await parser.parse_image(empty)

    @pytest.mark.asyncio
    async def test_png_uses_image_png_mime(self, tmp_path):
        img = tmp_path / "shot.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        parser = AIParser(make_settings())
        parser.router = make_router([make_provider("OpenAI", '[{"loan_number":"L1"}]')])
        await parser.parse_image(img)
        # Inspect the message payload passed to the provider.
        calls = parser.router.providers[0].client.completions.calls
        assert len(calls) == 1
        content = calls[0]["messages"][0]["content"]
        assert any("image/png" in str(item) for item in content)

    @pytest.mark.asyncio
    async def test_jpeg_uses_image_jpeg_mime(self, tmp_path):
        img = tmp_path / "shot.jpg"
        img.write_bytes(b"\xff\xd8\xff\xe0fake")
        parser = AIParser(make_settings())
        parser.router = make_router([make_provider("OpenAI", '[{"loan_number":"L1"}]')])
        await parser.parse_image(img)
        calls = parser.router.providers[0].client.completions.calls
        assert len(calls) == 1
        content = calls[0]["messages"][0]["content"]
        assert any("image/jpeg" in str(item) for item in content)

    @pytest.mark.asyncio
    async def test_vision_route_only_calls_vision_capable(self, tmp_path):
        img = tmp_path / "shot.png"
        img.write_bytes(b"\x89PNG\r\n\x1a\nfake")
        text_only = make_provider("Groq", "SHOULD NOT BE CALLED", supports_vision=False)
        vision = make_provider("OpenAI", '[{"loan_number":"L1"}]', supports_vision=True)
        parser = AIParser(make_settings())
        parser.router = make_router([text_only, vision])
        result = await parser.parse_image(img)
        assert result == [{"loan_number": "L1"}]
        assert text_only.client.completions.calls == []


# ---------------------------------------------------------------------------
# Sensitive data must not be logged
# ---------------------------------------------------------------------------

class TestSensitiveDataNotLogged:
    """Ensure customer PII never appears in log output."""

    @pytest.mark.asyncio
    async def test_success_path_logs_no_customer_data(self, caplog):
        parser = AIParser(make_settings())
        parser.router = make_router([
            make_provider("OpenAI", '[{"loan_number":"LN-SECRET-1","first_name":"Maria",'
                                     '"phone_numbers":["+15551234567"]}]')
        ])
        with caplog.at_level("INFO"):
            await parser.parse_text("Maria Gomez, loan LN-SECRET-1, phone +15551234567")
        combined = "\n".join(r.getMessage() for r in caplog.records)
        assert "LN-SECRET-1" not in combined
        assert "Maria" not in combined
        assert "15551234567" not in combined

    @pytest.mark.asyncio
    async def test_failure_path_logs_no_customer_data(self, caplog):
        parser = AIParser(make_settings())
        parser.router = make_router([
            make_provider("OpenAI", "x", raise_exc=make_rate_limit_error()),
            make_provider("Gemini", "x", raise_exc=make_api_error()),
        ])
        with caplog.at_level("ERROR"):
            with pytest.raises(ParserError):
                await parser.parse_text("Maria Gomez, loan LN-SECRET-2, phone +15559876543")
        combined = "\n".join(r.getMessage() for r in caplog.records)
        assert "LN-SECRET-2" not in combined
        assert "Maria" not in combined
        assert "15559876543" not in combined


# ---------------------------------------------------------------------------
# Prompt / schema consistency
# ---------------------------------------------------------------------------

class TestPromptSchemaConsistency:
    """Guard against drift between AI_PROMPT, SYSTEM_PROMPT, and the
    canonical STANDARD_KEYS schema."""

    def test_ai_prompt_contains_all_standard_keys(self):
        for key in STANDARD_KEYS:
            assert key in AI_PROMPT, f"AI_PROMPT missing key: {key}"

    def test_system_prompt_contains_all_standard_keys(self):
        for key in STANDARD_KEYS:
            assert key in SYSTEM_PROMPT, f"SYSTEM_PROMPT missing key: {key}"

    def test_map_common_keys_round_trip(self):
        raw = {key: f"val-{key}" for key in STANDARD_KEYS}
        mapped = _map_common_keys(raw)
        assert set(mapped.keys()) == set(STANDARD_KEYS)