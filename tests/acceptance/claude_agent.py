"""The real agent: the `claude` CLI, headless (`claude -p`), on a cheap model, held to the `kiripix` tool.

Isolation is enforced by flags, not asked for in the prompt (flags checked against `claude --help`, Claude Code 2.1):
- cwd is a temporary folder outside the repo (the harness also asserts no CLAUDE.md or .claude above it);
- `--safe-mode`: CLAUDE.md, memory, skills, plugins, hooks, MCP servers, custom commands and agents are off
  (`--bare` would do the same but reads only ANTHROPIC_API_KEY, and this machine logs in with OAuth);
- `--setting-sources local`: user and project settings files are not read (the temporary folder has no local one);
- `--strict-mcp-config` with no `--mcp-config`, and `--disable-slash-commands`, on top of safe mode;
- `--tools Bash`: Bash is the only built-in tool;
- `--allowedTools`: Bash only for the `kiripix` and `kpx` prefixes; `--permission-mode dontAsk` and
  `--permission-prompts none` deny everything else without asking, so `python`, `KIRIPIX_TEST_OWNER=1 kiripix` and reading
  the repo's files fail. A denied attempt is recorded. Claude Code still allows what it counts as read-only inside the
  temporary folder (`cd`, `echo`, `head`).
- the first stream event (`system` / `init`) is checked: any tool other than Bash, or any MCP server, ends the run.

The prompt goes in on stdin, because `--tools` and `--allowedTools` take a variable number of arguments and would swallow
a positional prompt.
"""

import json
import re
import shutil
import subprocess
import threading
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .harness import AgentTurn, CommandRun, Usage

DEFAULT_VERSION = "claude-haiku-5-5"
ALLOWED = "Bash(kiripix),Bash(kiripix *),Bash(kpx),Bash(kpx *)"
CALL_TIMEOUT_S = 20 * 60
DENIED_TEXT = re.compile(r"permission|denied|not allowed|don't have|haven't been granted", re.IGNORECASE)
EXIT_CODE = re.compile(r"^Exit code (\d+)")


def claude_args(version: str, max_usd: float, session: str, resume: bool) -> list[str]:
    """Every flag here must appear in `claude --help` (a test checks)."""
    return [
        "-p", "--output-format", "stream-json", "--verbose",
        "--model", version, "--max-budget-usd", str(max_usd),
        "--safe-mode", "--setting-sources", "local", "--strict-mcp-config", "--disable-slash-commands",
        "--tools", "Bash", "--allowedTools", ALLOWED,
        "--permission-mode", "dontAsk", "--permission-prompts", "none",
        "--resume" if resume else "--session-id", session,
    ]


def _usage(raw: Mapping[str, Any]) -> Usage:
    return Usage(int(raw.get("input_tokens") or 0), int(raw.get("output_tokens") or 0),
                 int(raw.get("cache_creation_input_tokens") or 0), int(raw.get("cache_read_input_tokens") or 0))


class Stream:
    """The state built from one invocation's stream-json events."""

    def __init__(self, turn: int = 0) -> None:
        self.turn = turn
        self.session_id: str | None = None
        self.init: dict[str, Any] = {}
        self.result: dict[str, Any] | None = None
        self.by_message: dict[str, Usage] = {}  # one assistant message is streamed once per content block
        self.calls: dict[str, CommandRun] = {}
        self.text = ""

    def feed(self, event: Mapping[str, Any]) -> None:
        kind = event.get("type")
        self.session_id = event.get("session_id") or self.session_id
        if kind == "system" and event.get("subtype") == "init":
            self.init = dict(event)
        elif kind == "assistant":
            message = event.get("message") or {}
            if message.get("usage"):
                self.by_message[str(message.get("id"))] = _usage(message["usage"])
            for block in message.get("content") or []:
                if block.get("type") == "text":
                    self.text = block.get("text", "")
                elif block.get("type") == "tool_use":
                    arguments = block.get("input") or {}
                    command = arguments.get("command") if block.get("name") == "Bash" else None
                    label = command if isinstance(command, str) else f"{block.get('name')} {json.dumps(arguments)}"
                    self.calls[block["id"]] = CommandRun(self.turn, label, None)
        elif kind == "user":
            content = (event.get("message") or {}).get("content")
            for block in content if isinstance(content, list) else []:
                if block.get("type") == "tool_result" and block.get("tool_use_id") in self.calls:
                    self._finish(self.calls[block["tool_use_id"]], block)
        elif kind == "result":
            self.result = dict(event)

    def _finish(self, run: CommandRun, block: Mapping[str, Any]) -> None:
        content = block.get("content")
        text = content if isinstance(content, str) else "\n".join(
            part.get("text", "") for part in content or [] if isinstance(part, dict))
        run.output = text.strip()
        if not block.get("is_error"):
            run.exit_code = 0
            return
        found = EXIT_CODE.match(run.output)
        if found:
            run.exit_code = int(found.group(1))
        elif DENIED_TEXT.search(run.output):
            run.denied = True

    @property
    def usage(self) -> Usage:
        """The result's own totals if it came, else the sum of the assistant messages seen so far."""
        if self.result and self.result.get("usage"):
            return _usage(self.result["usage"])
        total = Usage()
        for each in self.by_message.values():
            total.add(each)
        return total

    @property
    def live_fresh(self) -> int:
        total = Usage()
        for each in self.by_message.values():
            total.add(each)
        return total.fresh

    def commands(self) -> list[CommandRun]:
        for denial in (self.result or {}).get("permission_denials") or []:
            run = self.calls.get(denial.get("tool_use_id"))
            if run:
                run.denied = True
        return list(self.calls.values())

    def isolation_breach(self) -> str | None:
        """The init event lists what the agent has. Anything beyond Bash, or any MCP server, is a breach."""
        if not self.init:
            return "no init event: cannot confirm what tools the agent has"
        extra = sorted(set(self.init.get("tools") or []) - {"Bash"})
        servers = self.init.get("mcp_servers") or []
        if extra or servers:
            return f"the agent has more than Bash: tools {extra}, mcp_servers {servers}"
        return None


class ClaudeAgent:
    name = "claude -p (headless)"

    def __init__(self, agent_version: str = DEFAULT_VERSION, max_usd: float = 1.0, claude: str | None = None) -> None:
        self.agent_version = agent_version
        self.max_usd = max_usd
        self.claude = claude or shutil.which("claude") or "claude"
        self.session = str(uuid.uuid4())
        self.cwd = Path()
        self.env: Mapping[str, str] = {}
        self.turn = 0
        self.isolation = [
            "cwd is a temporary folder with no CLAUDE.md or .claude above it (asserted)",
            "--safe-mode (no CLAUDE.md, memory, skills, plugins, hooks, MCP, custom agents)",
            "--setting-sources local, --strict-mcp-config, --disable-slash-commands",
            "--tools Bash; Bash allowed only for the kiripix and kpx prefixes: " + ALLOWED,
            "--permission-mode dontAsk, --permission-prompts none: anything else is denied, except what Claude Code "
            "itself counts as read-only inside the temporary folder (cd, echo, head); reading the repo's files is denied",
            "env without KIRIPIX_TEST_OWNER and KIRIPIX_TEST_RECIPES; kiripix on PATH from the venv",
            "fake Runners (D16) through the shims `kiripix` and `kpx` first on PATH, which set them for that process only",
            "the init event is checked: Bash is the only tool, no MCP servers",
        ]

    def start(self, task: str, cwd: Path, env: Mapping[str, str], budget_left: int) -> AgentTurn:
        self.cwd, self.env = cwd, env
        return self._invoke(task, resume=False, budget_left=budget_left)

    def resume(self, message: str, budget_left: int) -> AgentTurn:
        return self._invoke(message, resume=True, budget_left=budget_left)

    def _invoke(self, prompt: str, resume: bool, budget_left: int) -> AgentTurn:
        self.turn += 1
        stream, turn = Stream(self.turn), AgentTurn(session_id=self.session)
        process = subprocess.Popen(
            [self.claude, *claude_args(self.agent_version, self.max_usd, self.session, resume)], cwd=self.cwd,
            env=dict(self.env), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8")
        assert process.stdin and process.stdout and process.stderr
        errors: list[str] = []
        threading.Thread(target=lambda: errors.append(process.stderr.read()) if process.stderr else None,
                         daemon=True).start()
        watchdog = threading.Timer(CALL_TIMEOUT_S, process.kill)
        watchdog.start()
        process.stdin.write(prompt)
        process.stdin.close()
        for line in process.stdout:
            try:
                stream.feed(json.loads(line))
            except json.JSONDecodeError:
                continue
            if turn.error is None and (breach := stream.isolation_breach() if stream.init else None):
                turn.error = f"isolation: {breach}"
                process.kill()
            elif stream.live_fresh > budget_left:
                turn.over_budget = True
                process.kill()
        code = process.wait()
        watchdog.cancel()
        if turn.error is None and stream.init == {}:
            turn.error = "isolation: " + (stream.isolation_breach() or "")
        if not (turn.over_budget or turn.error):
            result = stream.result
            if result is None:
                turn.error = f"claude exited {code} without a result; stderr: {''.join(errors).strip()[:500]}"
            elif result.get("is_error") or result.get("subtype") != "success":
                turn.error = f"claude ended with {result.get('subtype')}: {str(result.get('result'))[:500]}"
        turn.commands, turn.usage = stream.commands(), stream.usage
        turn.final_text = str((stream.result or {}).get("result") or stream.text)
        return turn
