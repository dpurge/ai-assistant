import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path

try:
    from google.adk.tools import ToolContext  # noqa: F401
except ModuleNotFoundError:
    adk_module = types.ModuleType("google.adk")
    tools_module = types.ModuleType("google.adk.tools")

    class ToolContext:
        pass

    tools_module.ToolContext = ToolContext
    sys.modules["google.adk"] = adk_module
    sys.modules["google.adk.tools"] = tools_module

TOOLS_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "app" / "agent" / "tools.py"
)
TOOLS_SPEC = importlib.util.spec_from_file_location("agent_tools", TOOLS_PATH)
tools = importlib.util.module_from_spec(TOOLS_SPEC)
assert TOOLS_SPEC.loader is not None
TOOLS_SPEC.loader.exec_module(tools)

MAX_PAGE_TEXT_CHARS = tools.MAX_PAGE_TEXT_CHARS
_extract_page_text = tools._extract_page_text


class FakeToolContext:
    def __init__(self):
        self.state = {}


class ExtractPageTextTest(unittest.TestCase):
    def test_extracts_title_and_article_text(self):
        title, content = _extract_page_text(
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

        self.assertEqual(title, "City Guide")
        self.assertIn("A day in Krakow", content)
        self.assertIn("Start near the river.", content)
        self.assertIn("Order pierogi at lunch.", content)
        self.assertNotIn("Menu Login", content)
        self.assertNotIn("Copyright", content)

    def test_falls_back_to_body(self):
        title, content = _extract_page_text(
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

        self.assertEqual(title, "")
        self.assertIn("Market vocabulary", content)
        self.assertIn("Apples are cheap today.", content)

    def test_removes_noisy_elements(self):
        _, content = _extract_page_text(
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

        self.assertEqual(content, "Readable lesson source.")

    def test_long_content_can_be_truncated_by_tool_limit(self):
        word_count = (MAX_PAGE_TEXT_CHARS // len("word ")) + 100
        _, content = _extract_page_text(
            f"<article>{'word ' * word_count}</article>"
        )

        truncated = len(content) > MAX_PAGE_TEXT_CHARS
        limited = content[:MAX_PAGE_TEXT_CHARS].rstrip()

        self.assertTrue(truncated)
        self.assertLessEqual(len(limited), MAX_PAGE_TEXT_CHARS)

    def test_read_web_page_error_records_failure_state(self):
        context = FakeToolContext()

        result = tools.read_web_page("not-a-url", context)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["tool"], "read_web_page")
        self.assertTrue(context.state[tools.TOOL_CALL_FAILED_KEY])
        self.assertIn(
            "Please paste the text or provide another URL.",
            context.state[tools.TOOL_CALL_ERROR_MESSAGE_KEY],
        )

    def test_tool_success_clears_failure_state(self):
        context = FakeToolContext()
        context.state[tools.TOOL_CALL_FAILED_KEY] = True
        context.state[tools.TOOL_CALL_ERROR_MESSAGE_KEY] = "previous error"

        tools._record_tool_success(context)

        self.assertFalse(context.state[tools.TOOL_CALL_FAILED_KEY])
        self.assertEqual(context.state[tools.TOOL_CALL_ERROR_MESSAGE_KEY], "")

    def test_read_file_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "lesson.txt"
            path.write_text("Lesson text", encoding="utf-8")
            context = FakeToolContext()

            result = tools.read_file(str(path), context)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["content"], "Lesson text")
        self.assertFalse(result["truncated"])
        self.assertFalse(context.state[tools.TOOL_CALL_FAILED_KEY])

    def test_read_file_missing_records_failure_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "missing.txt"
            context = FakeToolContext()

            result = tools.read_file(str(path), context)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["tool"], "read_file")
        self.assertTrue(context.state[tools.TOOL_CALL_FAILED_KEY])
        self.assertIn(
            "Please provide another file path or paste the text.",
            context.state[tools.TOOL_CALL_ERROR_MESSAGE_KEY],
        )

    def test_write_file_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nested" / "lesson.txt"
            context = FakeToolContext()

            result = tools.write_file(str(path), "Saved lesson", context)
            saved_text = path.read_text(encoding="utf-8")

        self.assertEqual(result["status"], "success")
        self.assertEqual(
            result["bytes_written"],
            len("Saved lesson".encode("utf-8")),
        )
        self.assertEqual(saved_text, "Saved lesson")
        self.assertFalse(context.state[tools.TOOL_CALL_FAILED_KEY])

    def test_write_file_directory_records_failure_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            context = FakeToolContext()

            result = tools.write_file(tmpdir, "Saved lesson", context)

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["tool"], "write_file")
        self.assertTrue(context.state[tools.TOOL_CALL_FAILED_KEY])
        self.assertIn(
            "Please provide a writable file path.",
            context.state[tools.TOOL_CALL_ERROR_MESSAGE_KEY],
        )


if __name__ == "__main__":
    unittest.main()
