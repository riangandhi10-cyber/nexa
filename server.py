#!/usr/bin/env python3
"""Standalone AI chatbot — web search, images, and OpenAI answers."""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
from aiohttp import web

from search import format_search_context, search_images, search_provider, search_web

ROOT = Path(__file__).resolve().parent
_DEFAULT_MODEL = "gpt-5.5"
_MAX_MESSAGES = 50
_MAX_CHARS = 8000
_DEFAULT_SYSTEM = (
    "You are Nexa, a detailed research assistant with access to live web search results. "
    "Use the provided search results to give thorough, accurate, well-structured answers. "
    "Include specific facts: names, dates, numbers, locations, and key details. "
    "For complex topics use markdown headers and bullet points. "
    "Write 2-5 paragraphs when the question warrants detail. "
    "Synthesize everything into one complete answer — never tell the user to search elsewhere. "
    "If search results are sparse, combine them with your knowledge and note any uncertainty."
)


def _load_dotenv() -> None:
    path = ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = val


def _ai_configured() -> bool:
    return bool(os.environ.get("OPENAI_API_KEY", "").strip())


def _sanitize_messages(raw: list) -> list[dict[str, str]]:
    allowed = {"user", "assistant"}
    out: list[dict[str, str]] = []
    for item in raw[-_MAX_MESSAGES:]:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        if role not in allowed:
            continue
        content = str(item.get("content") or "").strip()
        if not content:
            continue
        if len(content) > _MAX_CHARS:
            content = content[:_MAX_CHARS]
        out.append({"role": role, "content": content})
    return out


async def _call_openai(
    session: aiohttp.ClientSession,
    *,
    url: str,
    headers: dict[str, str],
    model: str,
    system: str,
    messages: list[dict[str, str]],
) -> str:
    max_out = min(int(os.environ.get("OPENAI_MAX_TOKENS", "2500")), 4000)
    payload: dict = {
        "model": model,
        "messages": [{"role": "system", "content": system}, *messages],
        "max_completion_tokens": max_out,
    }
    # GPT-5+ only supports default temperature (1); omit for those models.
    if not model.startswith(("gpt-5", "o1", "o3", "o4")):
        payload["temperature"] = 0.7
    async with session.post(url, json=payload, headers=headers) as resp:
        data = await resp.json(content_type=None)
        if resp.status >= 400:
            err = data.get("error", {}) if isinstance(data, dict) else {}
            msg = err.get("message") if isinstance(err, dict) else str(data)
            raise RuntimeError(msg or f"AI request failed ({resp.status})")
        choices = data.get("choices") if isinstance(data, dict) else None
        if not choices:
            raise RuntimeError("Empty AI response")
        reply = (choices[0].get("message", {}).get("content") or "").strip()
        if not reply:
            raise RuntimeError("Empty AI response")
        return reply


async def logo(_request: web.Request) -> web.FileResponse:
    return web.FileResponse(ROOT / "logo.png")


async def index(_request: web.Request) -> web.FileResponse:
    return web.FileResponse(ROOT / "index.html")


async def api_status(_request: web.Request) -> web.Response:
    configured = _ai_configured()
    return web.json_response(
        {
            "configured": configured,
            "mode": "openai" if configured else "local",
            "model": os.environ.get("OPENAI_MODEL", _DEFAULT_MODEL),
            "search": search_provider(),
        }
    )


async def api_health(_request: web.Request) -> web.Response:
    return web.json_response({"ok": True, "name": "Nexa"})


async def api_image_proxy(request: web.Request) -> web.StreamResponse:
    raw = str(request.query.get("url") or "").strip()
    if not raw.startswith(("http://", "https://")):
        raise web.HTTPBadRequest(text="Invalid url")
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(raw, headers={"User-Agent": "Mozilla/5.0"}) as resp:
            if resp.status >= 400:
                raise web.HTTPBadGateway()
            body = await resp.read()
            content_type = resp.headers.get("Content-Type", "image/jpeg")
    return web.Response(body=body, content_type=content_type)


async def api_run(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    lang = str(body.get("lang") or "python").strip().lower()
    code = str(body.get("code") or "")[:10000]
    if not code.strip():
        return web.json_response({"error": "No code provided"}, status=400)
    if lang not in ("python", "py"):
        return web.json_response(
            {"error": "Server runs Python only. JavaScript and HTML run in your browser."},
            status=400,
        )

    import asyncio
    import subprocess
    import tempfile

    def _run_python() -> dict:
        path = ""
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as f:
                f.write(code)
                path = f.name
            proc = subprocess.run(
                ["python3", path],
                capture_output=True,
                text=True,
                timeout=8,
            )
            out = proc.stdout or ""
            if proc.stderr:
                out = (out + "\n" if out else "") + proc.stderr
            return {
                "ok": proc.returncode == 0,
                "output": out.strip() or "(no output)",
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "output": "Timed out (8 second limit)"}
        except Exception as e:
            return {"ok": False, "output": str(e)}
        finally:
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass

    loop = asyncio.get_running_loop()
    result = await loop.run_in_executor(None, _run_python)
    return web.json_response(result)


async def api_chat(request: web.Request) -> web.Response:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"error": "Invalid JSON"}, status=400)

    messages = _sanitize_messages(body.get("messages") or [])
    if not messages or messages[-1]["role"] != "user":
        return web.json_response({"error": "Last message must be from user"}, status=400)

    user_prompt = str(body.get("systemPrompt") or "").strip()[:2000]
    system = _DEFAULT_SYSTEM
    if user_prompt:
        system = user_prompt + "\n\n" + _DEFAULT_SYSTEM

    if not _ai_configured():
        return web.json_response(
            {
                "error": "No API key configured. Set OPENAI_API_KEY in Render environment variables.",
                "mode": "local",
            },
            status=503,
        )

    question = messages[-1]["content"]
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("OPENAI_MODEL", _DEFAULT_MODEL)
    url = f"{base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {os.environ['OPENAI_API_KEY'].strip()}",
        "Content-Type": "application/json",
    }

    try:
        timeout = aiohttp.ClientTimeout(total=120)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            web_results, provider = await search_web(session, question)
            images = await search_images(session, question)
            search_block = format_search_context(web_results)
            enriched_system = (
                f"{system}\n\n---\n{search_block}\n---\n"
                "Answer using the search results above when available. Be detailed and specific."
            )
            reply = await _call_openai(
                session,
                url=url,
                headers=headers,
                model=model,
                system=enriched_system,
                messages=messages,
            )
            sources = [
                {"title": r["title"], "url": r["url"]}
                for r in web_results
                if r.get("url")
            ][:6]
            return web.json_response(
                {
                    "reply": reply,
                    "mode": "openai",
                    "search": provider,
                    "sources": sources,
                    "images": images[:6],
                }
            )
    except RuntimeError as e:
        return web.json_response({"error": str(e)}, status=502)
    except aiohttp.ClientError as e:
        return web.json_response({"error": f"Could not reach AI service: {e}"}, status=502)
    except (TimeoutError, aiohttp.ServerTimeoutError):
        return web.json_response({"error": "AI request timed out"}, status=504)


def main() -> None:
    _load_dotenv()
    app = web.Application()
    app.router.add_get("/logo.png", logo)
    app.router.add_get("/", index)
    app.router.add_get("/api/health", api_health)
    app.router.add_get("/api/status", api_status)
    app.router.add_get("/api/image", api_image_proxy)
    app.router.add_post("/api/run", api_run)
    app.router.add_post("/api/chat", api_chat)
    port = int(os.environ.get("PORT", "8090"))
    host = os.environ.get("HOST", "0.0.0.0")
    if _ai_configured():
        model = os.environ.get("OPENAI_MODEL", _DEFAULT_MODEL)
        src = search_provider()
        print(f"Nexa ready — http://{host}:{port} (model: {model}, search: {src})")
    else:
        print(f"Nexa ready — http://{host}:{port} (set OPENAI_API_KEY)")
    web.run_app(app, host=host, port=port, print=None)


if __name__ == "__main__":
    main()
