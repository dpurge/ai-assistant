import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import google.auth
import httpx
from bs4 import BeautifulSoup
from google.adk.tools import ToolContext


MAX_PAGE_TEXT_CHARS = 100_000
MAX_FILE_TEXT_CHARS = 100_000
FETCH_TIMEOUT_SECONDS = 10.0
VERIFY_SSL_CERTIFICATES = False
TOOL_CALL_FAILED_KEY = "tool_call_failed"
TOOL_CALL_ERROR_MESSAGE_KEY = "tool_call_error_message"
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


# def setup(vertexai=True):
#     if vertexai:
#         _, project_id = google.auth.default()
#         os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id)
#         os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
#         os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")
#         log("Set up environment for Vertex AI")
#     else:
#         os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "False")
#         log("Set up environment for Gemini API")


# def log(message: str):
#     return None


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
    path = Path(filename).expanduser()
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

    truncated = len(content) > MAX_FILE_TEXT_CHARS
    if truncated:
        content = content[:MAX_FILE_TEXT_CHARS].rstrip()

    _record_tool_success(tool_context)
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

    _record_tool_success(tool_context)
    return {
        "status": "success",
        "filename": str(path),
        "bytes_written": len(content.encode("utf-8")),
    }


def read_web_page(url: str, tool_context: ToolContext) -> dict[str, Any]:
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

    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=FETCH_TIMEOUT_SECONDS,
            verify=VERIFY_SSL_CERTIFICATES,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            response = client.get(normalized_url)
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

    truncated = len(content) > MAX_PAGE_TEXT_CHARS
    if truncated:
        content = content[:MAX_PAGE_TEXT_CHARS].rstrip()

    _record_tool_success(tool_context)

    return {
        "status": "success",
        "url": str(response.url),
        "title": title,
        "content": content,
        "truncated": truncated,
    }


def _record_tool_success(tool_context: ToolContext) -> None:
    tool_context.state[TOOL_CALL_FAILED_KEY] = False
    tool_context.state[TOOL_CALL_ERROR_MESSAGE_KEY] = ""


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
    tool_context.state[TOOL_CALL_FAILED_KEY] = True
    tool_context.state[TOOL_CALL_ERROR_MESSAGE_KEY] = user_message

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
