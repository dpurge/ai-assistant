"""Tools available to the language-tutor pipeline.

``read_web_page`` is async because it runs inside ADK's asyncio loop; using
``httpx.AsyncClient`` keeps a slow upstream from blocking concurrent chats.
``read_file`` / ``write_file`` stay synchronous - stdlib has no async file API
and lesson source files are small.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from google.adk.tools import ToolContext

from app.agent.state import (
    TOOL_CALL_ERROR_MESSAGE_KEY,
    TOOL_CALL_FAILED_KEY,
    clear_tool_call_status,
    mark_tool_call_failed,
)
from app.config import get_settings

logger = logging.getLogger(__name__)


USER_AGENT = (
    "Mozilla/5.0 (compatible; ai-tutor/0.1; "
    "+https://localhost.localdomain/ai-tutor)"
)
READABLE_CONTENT_SELECTORS = ("article", "main", '[role="main"]')
NOISY_SELECTORS = (
    "script",
    "style",
    "template",
    "noscript",
    "nav",
    "footer",
    "header",
    "aside",
    "form",
    "svg",
    "iframe",
    "canvas",
)

__all__ = [
    "TOOL_CALL_ERROR_MESSAGE_KEY",
    "TOOL_CALL_FAILED_KEY",
    "read_file",
    "read_web_page",
    "write_file",
]


def read_file(filename: str, tool_context: ToolContext) -> dict[str, Any]:
    """Reads a UTF-8 text file and returns its content.

    Use this tool when the user provides a local file path as source material.

    Args:
        filename: The file path to read.

    Returns:
        A dictionary with status 'success' or 'error'. Successful results
        include filename, content, and truncated. Error results include
        error_message.
    """
    settings = get_settings()
    path = Path(filename).expanduser()
    logger.info("read_file: %s", path)
    try:
        if path.is_dir():
            return _tool_error(
                "read_file",
                "The file could not be read",
                f"{path} is a directory.",
                tool_context,
                filename=str(path),
                user_action="Please provide a text file path or paste the text.",
            )

        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return _tool_error(
            "read_file",
            "The file could not be read",
            f"{path} is not valid UTF-8 text: {exc}.",
            tool_context,
            filename=str(path),
            user_action="Please provide a UTF-8 text file or paste the text.",
        )
    except OSError as exc:
        return _tool_error(
            "read_file",
            "The file could not be read",
            f"{path}: {exc.strerror or exc}.",
            tool_context,
            filename=str(path),
            user_action="Please provide another file path or paste the text.",
        )

    max_chars = settings.max_file_text_chars
    truncated = len(content) > max_chars
    if truncated:
        content = content[:max_chars].rstrip()

    clear_tool_call_status(tool_context.state)
    logger.info("read_file ok: %s (%d chars, truncated=%s)", path, len(content), truncated)
    return {
        "status": "success",
        "filename": str(path),
        "content": content,
        "truncated": truncated,
    }


def write_file(
    filename: str,
    content: str,
    tool_context: ToolContext,
) -> dict[str, Any]:
    """Writes UTF-8 text content to a file.

    Use this tool only when the user explicitly asks to save content to a
    local file path.

    Args:
        filename: The file path to write.
        content: The text content to write.

    Returns:
        A dictionary with status 'success' or 'error'. Successful results
        include filename and bytes_written. Error results include error_message.
    """
    path = Path(filename).expanduser()
    logger.info("write_file: %s", path)
    try:
        if path.exists() and path.is_dir():
            return _tool_error(
                "write_file",
                "The file could not be written",
                f"{path} is a directory.",
                tool_context,
                filename=str(path),
                user_action="Please provide a writable file path.",
            )

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        return _tool_error(
            "write_file",
            "The file could not be written",
            f"{path}: {exc.strerror or exc}.",
            tool_context,
            filename=str(path),
            user_action="Please provide another writable file path.",
        )

    clear_tool_call_status(tool_context.state)
    bytes_written = len(content.encode("utf-8"))
    logger.info("write_file ok: %s (%d bytes)", path, bytes_written)
    return {
        "status": "success",
        "filename": str(path),
        "bytes_written": bytes_written,
    }


async def read_web_page(url: str, tool_context: ToolContext) -> dict[str, Any]:
    """Fetches a web page and returns readable text for language lesson writing.

    Use this tool when the user provides an HTTP or HTTPS URL and wants the
    page adapted into lesson text. The tool reads static page content only; it
    does not render JavaScript-only pages or authenticate.

    Args:
        url: The full HTTP or HTTPS URL to read.

    Returns:
        A dictionary with status 'success' or 'error'. Successful results include
        url, title, content, and truncated. Error results include error_message.
    """
    settings = get_settings()
    normalized_url = url.strip()
    parsed_url = urlparse(normalized_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        return _tool_error(
            "read_web_page",
            "The web page could not be read",
            "Only full HTTP and HTTPS URLs can be read.",
            tool_context,
            url=normalized_url,
            user_action="Please paste the text or provide another URL.",
        )

    logger.info("read_web_page: %s", normalized_url)
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=settings.fetch_timeout_seconds,
            verify=settings.verify_ssl_certificates,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            response = await client.get(normalized_url)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        return _tool_error(
            "read_web_page",
            "The web page could not be read",
            f"HTTP {exc.response.status_code} while reading the page.",
            tool_context,
            url=normalized_url,
            user_action="Please paste the text or provide another URL.",
        )
    except httpx.RequestError as exc:
        return _tool_error(
            "read_web_page",
            "The web page could not be read",
            f"Could not read the page: {exc}.",
            tool_context,
            url=normalized_url,
            user_action="Please paste the text or provide another URL.",
        )

    content_type = response.headers.get("content-type", "")
    if content_type and not _is_text_content_type(content_type):
        return _tool_error(
            "read_web_page",
            "The web page could not be read",
            f"Unsupported content type: {content_type}.",
            tool_context,
            url=str(response.url),
            user_action="Please paste the text or provide another URL.",
        )

    title, content = _extract_page_text(response.text)
    if not content:
        return _tool_error(
            "read_web_page",
            "The web page could not be read",
            "No readable text was found on the page.",
            tool_context,
            url=str(response.url),
            user_action="Please paste the text or provide another URL.",
            title=title,
        )

    max_chars = settings.max_page_text_chars
    truncated = len(content) > max_chars
    if truncated:
        content = content[:max_chars].rstrip()

    clear_tool_call_status(tool_context.state)
    logger.info(
        "read_web_page ok: %s (title=%r, %d chars, truncated=%s)",
        response.url,
        title,
        len(content),
        truncated,
    )

    return {
        "status": "success",
        "url": str(response.url),
        "title": title,
        "content": content,
        "truncated": truncated,
    }


def _tool_error(
    tool_name: str,
    failure_summary: str,
    error_message: str,
    tool_context: ToolContext,
    *,
    user_action: str,
    url: str | None = None,
    filename: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    user_message = f"{failure_summary}: {error_message} {user_action}"
    mark_tool_call_failed(tool_context.state, user_message)
    logger.warning("%s failed: %s", tool_name, error_message)

    result = {
        "status": "error",
        "tool": tool_name,
        "error_message": error_message,
    }
    if url is not None:
        result["url"] = url
    if filename is not None:
        result["filename"] = filename
    if title is not None:
        result["title"] = title

    return result


def _record_tool_success(tool_context: ToolContext) -> None:
    """Backwards-compatible shim used by the test suite."""
    clear_tool_call_status(tool_context.state)


def _is_text_content_type(content_type: str) -> bool:
    return any(
        content_type.lower().startswith(prefix)
        for prefix in ("text/html", "text/plain", "application/xhtml+xml")
    )


def _extract_page_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")

    for element in soup.select(", ".join(NOISY_SELECTORS)):
        element.decompose()

    title = ""
    if soup.title:
        title = _clean_text(soup.title.get_text(" ", strip=True))

    content_root = None
    for selector in READABLE_CONTENT_SELECTORS:
        content_root = soup.select_one(selector)
        if content_root is not None:
            break

    if content_root is None:
        content_root = soup.body or soup

    content = _clean_text(content_root.get_text("\n", strip=True))
    return title, content


def _clean_text(text: str) -> str:
    normalized_lines = []
    for line in text.splitlines():
        normalized_line = re.sub(r"[ \t\r\f\v]+", " ", line).strip()
        if normalized_line:
            normalized_lines.append(normalized_line)

    return "\n".join(normalized_lines)


def _get_max_page_text_chars() -> int:
    return get_settings().max_page_text_chars


def _get_max_file_text_chars() -> int:
    return get_settings().max_file_text_chars


# Backwards-compatible aliases for tests that read the limits as module attrs.
MAX_PAGE_TEXT_CHARS = _get_max_page_text_chars()
MAX_FILE_TEXT_CHARS = _get_max_file_text_chars()
