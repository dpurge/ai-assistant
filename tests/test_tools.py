from __future__ import annotations

from pathlib import Path

import pytest

from app.agent import tools
from app.agent.state import TOOL_CALL_ERROR_MESSAGE_KEY, TOOL_CALL_FAILED_KEY


def test_extracts_title_and_article_text():
    title, content = tools._extract_page_text(
        """
        <html>
          <head><title>  City Guide  </title></head>
          <body>
            <nav>Menu Login</nav>
            <article>
              <h1>A day in Krakow</h1>
              <p>Start near the river.</p>
              <p>Order pierogi at lunch.</p>
            </article>
            <footer>Copyright</footer>
          </body>
        </html>
        """
    )

    assert title == "City Guide"
    assert "A day in Krakow" in content
    assert "Start near the river." in content
    assert "Order pierogi at lunch." in content
    assert "Menu Login" not in content
    assert "Copyright" not in content


def test_extract_page_text_falls_back_to_body():
    title, content = tools._extract_page_text(
        """
        <html>
          <body>
            <section>
              <h2>Market vocabulary</h2>
              <p>Apples are cheap today.</p>
            </section>
          </body>
        </html>
        """
    )

    assert title == ""
    assert "Market vocabulary" in content
    assert "Apples are cheap today." in content


def test_extract_page_text_removes_noisy_elements():
    _, content = tools._extract_page_text(
        """
        <main>
          <script>alert("noise")</script>
          <style>body { color: red; }</style>
          <aside>Related links</aside>
          <form>Subscribe</form>
          <p>Readable lesson source.</p>
        </main>
        """
    )

    assert content == "Readable lesson source."


def test_long_content_can_be_truncated_by_tool_limit():
    max_chars = tools._get_max_page_text_chars()
    word_count = (max_chars // len("word ")) + 100
    _, content = tools._extract_page_text(f"<article>{'word ' * word_count}</article>")

    assert len(content) > max_chars
    assert len(content[:max_chars].rstrip()) <= max_chars


@pytest.mark.asyncio
async def test_read_web_page_rejects_non_http_url(fake_tool_context):
    result = await tools.read_web_page("not-a-url", fake_tool_context)

    assert result["status"] == "error"
    assert result["tool"] == "read_web_page"
    assert fake_tool_context.state[TOOL_CALL_FAILED_KEY] is True
    assert (
        "Please paste the text or provide another URL."
        in fake_tool_context.state[TOOL_CALL_ERROR_MESSAGE_KEY]
    )


def test_record_tool_success_clears_failure_state(fake_tool_context):
    fake_tool_context.state[TOOL_CALL_FAILED_KEY] = True
    fake_tool_context.state[TOOL_CALL_ERROR_MESSAGE_KEY] = "previous error"

    tools._record_tool_success(fake_tool_context)

    assert fake_tool_context.state[TOOL_CALL_FAILED_KEY] is False
    assert fake_tool_context.state[TOOL_CALL_ERROR_MESSAGE_KEY] == ""


def test_read_file_success(tmp_path: Path, fake_tool_context):
    path = tmp_path / "lesson.txt"
    path.write_text("Lesson text", encoding="utf-8")

    result = tools.read_file(str(path), fake_tool_context)

    assert result["status"] == "success"
    assert result["content"] == "Lesson text"
    assert result["truncated"] is False
    assert fake_tool_context.state[TOOL_CALL_FAILED_KEY] is False


def test_read_file_missing_records_failure_state(tmp_path: Path, fake_tool_context):
    path = tmp_path / "missing.txt"

    result = tools.read_file(str(path), fake_tool_context)

    assert result["status"] == "error"
    assert result["tool"] == "read_file"
    assert fake_tool_context.state[TOOL_CALL_FAILED_KEY] is True
    assert (
        "Please provide another file path or paste the text."
        in fake_tool_context.state[TOOL_CALL_ERROR_MESSAGE_KEY]
    )


def test_write_file_success(tmp_path: Path, fake_tool_context):
    path = tmp_path / "nested" / "lesson.txt"

    result = tools.write_file(str(path), "Saved lesson", fake_tool_context)

    assert result["status"] == "success"
    assert result["bytes_written"] == len(b"Saved lesson")
    assert path.read_text(encoding="utf-8") == "Saved lesson"
    assert fake_tool_context.state[TOOL_CALL_FAILED_KEY] is False


def test_write_file_directory_records_failure_state(tmp_path: Path, fake_tool_context):
    result = tools.write_file(str(tmp_path), "Saved lesson", fake_tool_context)

    assert result["status"] == "error"
    assert result["tool"] == "write_file"
    assert fake_tool_context.state[TOOL_CALL_FAILED_KEY] is True
    assert (
        "Please provide a writable file path."
        in fake_tool_context.state[TOOL_CALL_ERROR_MESSAGE_KEY]
    )
