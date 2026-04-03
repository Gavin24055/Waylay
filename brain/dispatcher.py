"""
J — Dispatcher
Parses LLM JSON responses and routes to the correct skill function.
Includes tool result data in spoken responses (not just LLM's generic speak text).
"""

import json
import logging

logger = logging.getLogger("j.brain.dispatcher")

# Tools whose results should be spoken to the user (data-returning tools)
DATA_TOOLS = {
    "get_weather", "get_time", "get_system_stats", "get_clipboard",
    "get_active_window", "web_search", "web_fetch", "read_emails",
    "search_emails", "get_calendar_events", "phone_get_notifications",
    "phone_battery", "health_summary", "budget_status", "savings_progress",
    "stock_price", "finance_report", "project_status", "get_tasks_today",
    "git_summary", "f1_schedule", "f1_standings", "f1_news",
    "network_connections", "process_list", "system_audit", "cve_digest",
    "read_screen_text", "memory_recall", "memory_get_person",
}


class Dispatcher:
    """Parses LLM output and dispatches tool calls to the skills registry."""

    def __init__(self, skills_registry: dict, tts=None):
        self.registry = skills_registry
        self.tts = tts

    def dispatch(self, llm_response: str) -> str:
        """
        Parse the LLM response and execute tools if requested.
        Returns the text to speak — includes tool result data for data-returning tools.
        """
        logger.info("Dispatcher received LLM response: %s", llm_response[:200])

        # Try to parse as JSON
        parsed = self._try_parse_json(llm_response)

        if parsed is None:
            logger.info("Plain text response (no JSON found)")
            return llm_response.strip()

        thought = parsed.get("thought", "")
        tool_name = parsed.get("tool")
        params = parsed.get("params", {})
        speak_text = parsed.get("speak", "")
        display_text = parsed.get("display")

        if thought:
            logger.info("LLM thought: %s", thought)
        if display_text:
            logger.info("Display text: %s", display_text)

        if tool_name and tool_name != "null":
            logger.info("Dispatching tool: %s with params: %s", tool_name, params)
            result = self._execute_tool(tool_name, params)

            if result is not None:
                logger.info("Tool result: %s", str(result)[:200])

                # For data-returning tools, INCLUDE the tool result in speech
                # so J actually tells you the weather, time, etc.
                if tool_name in DATA_TOOLS:
                    result_str = str(result)[:300]
                    if speak_text:
                        # Combine: "Current weather — Bengaluru: Clear sky, 25°C..."
                        return f"{speak_text}. {result_str}"
                    return result_str

                # For action tools, check if the tool actually FAILED
                result_str = str(result)
                if self._is_tool_failure(result_str):
                    logger.warning("Tool %s failed: %s", tool_name, result_str[:100])
                    return result_str[:200]

                # Tool succeeded — use LLM's speak text
                if speak_text:
                    return speak_text
                return f"Done. {result_str[:100]}" if result else "Done."
            else:
                logger.warning("Tool %s returned None", tool_name)
                return speak_text or "I tried but something went wrong."
        else:
            logger.info("No tool needed, speak text: %s", speak_text[:100] if speak_text else "(empty)")
            return speak_text or llm_response.strip()

    @staticmethod
    def _is_tool_failure(result: str) -> bool:
        """Detect if a tool result indicates failure."""
        fail_keywords = [
            "not in the approved safe list",
            "failed", "error", "permission denied",
            "couldn't find", "not found", "timed out",
            "unavailable", "blocked",
        ]
        lower = result.lower()
        return any(kw in lower for kw in fail_keywords)

    def _try_parse_json(self, text: str) -> dict | None:
        """Try to extract JSON from the response."""
        text = text.strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        if "```json" in text:
            try:
                json_str = text.split("```json")[1].split("```")[0].strip()
                return json.loads(json_str)
            except (IndexError, json.JSONDecodeError):
                pass

        if "```" in text:
            try:
                json_str = text.split("```")[1].split("```")[0].strip()
                return json.loads(json_str)
            except (IndexError, json.JSONDecodeError):
                pass

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass

        return None

    def _execute_tool(self, tool_name: str, params: dict):
        """Look up and execute a tool from the skills registry."""
        if tool_name not in self.registry:
            logger.warning("Unknown tool: %s (available: %s)", tool_name, list(self.registry.keys())[:10])
            return None

        func = self.registry[tool_name]
        try:
            logger.info("Calling %s(**%s)", tool_name, params)
            result = func(**params)
            logger.info("Tool %s completed successfully", tool_name)
            return result
        except TypeError as e:
            logger.error("Tool parameter error for %s: %s", tool_name, e)
            try:
                return func(params)
            except Exception:
                return None
        except Exception as e:
            logger.error("Tool execution error for %s: %s", tool_name, e, exc_info=True)
            return None
