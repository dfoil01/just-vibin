#!/usr/bin/env python3
"""vibe-coder: Terminal Claude Code simulator. Fakes a convincing AI coding session."""

import sys
import time
import random
import json
import os

import anthropic
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.spinner import Spinner
from rich.live import Live
from rich.text import Text
from rich.columns import Columns
from rich import print as rprint

console = Console()

SPEED_MULT = 1.0  # set to 10.0 with --slow

def _sleep(seconds: float):
    time.sleep(seconds * SPEED_MULT)

def _uniform(lo: float, hi: float) -> float:
    return random.uniform(lo, hi) * SPEED_MULT

DEFAULT_TOPICS = [
    "refactor auth module to support MFA",
    "add stripe billing webhooks",
    "migrate database schema to support multi-tenancy",
    "implement rate limiting middleware",
    "add oauth2 login flow",
    "extract payment service into microservice",
    "add redis caching layer to API",
    "implement websocket notifications",
    "add CSV export feature",
    "refactor error handling to use structured logging",
]

SEED_PROMPT = """You are generating a realistic simulation seed for a fake Claude Code terminal session.
Given the topic: "{topic}"

Return ONLY valid JSON (no markdown, no explanation) with this exact structure:
{{
  "project_summary": "one sentence describing the coding task",
  "files": [
    {{"path": "src/...", "language": "python", "lines": 150, "purpose": "brief purpose"}},
    {{"path": "src/...", "language": "python", "lines": 80, "purpose": "brief purpose"}},
    {{"path": "tests/...", "language": "python", "lines": 120, "purpose": "test file"}},
    {{"path": "src/...", "language": "python", "lines": 45, "purpose": "brief purpose"}}
  ],
  "plan_steps": [
    {{"summary": "Read existing handler", "tool": "Read", "file": "src/...", "lines": 150}},
    {{"summary": "Search for related patterns", "tool": "Glob", "pattern": "src/**/*.py", "results": ["src/a.py", "src/b.py"]}},
    {{"summary": "Edit main handler to add feature", "tool": "Edit", "file": "src/...", "diff_hint": "add new function after line 45"}},
    {{"summary": "Run tests", "tool": "Bash", "cmd": "pytest tests/ -v", "output_hint": "all pass"}},
    {{"summary": "Check for linting issues", "tool": "Bash", "cmd": "ruff check src/", "output_hint": "clean"}},
    {{"summary": "Update secondary file", "tool": "Edit", "file": "src/...", "diff_hint": "import and call new function"}},
    {{"summary": "Run full test suite", "tool": "Bash", "cmd": "pytest -x --tb=short", "output_hint": "all pass"}}
  ],
  "functions": ["main_function", "helper_one", "helper_two", "validate_input"],
  "test_output_summary": "12 passed, 2 skipped",
  "files_changed": 2,
  "lines_changed": 38
}}

Make the paths realistic for the topic (e.g. src/auth/, src/payments/, tests/). Use Python conventions."""


def _local_seed(topic: str) -> dict:
    """Generate a plausible seed locally without an API call."""
    words = [w.lower() for w in topic.split()]
    # Pick a domain slug from the topic words
    domain_words = [w for w in words if w not in ("add","the","a","an","to","for","with","and","or","of","in","on")]
    slug = domain_words[0] if domain_words else "core"
    slug2 = domain_words[1] if len(domain_words) > 1 else "utils"

    src = f"src/{slug}"
    tests = f"tests/test_{slug}.py"
    files = [
        {"path": f"{src}/handler.py",   "language": "python", "lines": random.randint(140, 320), "purpose": f"main {slug} logic"},
        {"path": f"{src}/models.py",    "language": "python", "lines": random.randint(60, 120),  "purpose": "data models"},
        {"path": f"{src}/{slug2}.py",   "language": "python", "lines": random.randint(50, 100),  "purpose": "helper utilities"},
        {"path": tests,                 "language": "python", "lines": random.randint(80, 180),  "purpose": "test suite"},
    ]
    passed = random.randint(8, 22)
    skipped = random.randint(0, 3)
    plan_steps = [
        {"summary": f"Read existing {slug} handler", "tool": "Read",
         "file": f"{src}/handler.py", "lines": files[0]["lines"]},
        {"summary": f"Search for {slug} patterns", "tool": "Glob",
         "pattern": f"{src}/**/*.py", "results": [f["path"] for f in files[:3]]},
        {"summary": f"Edit handler to implement {topic}", "tool": "Edit",
         "file": f"{src}/handler.py", "diff_hint": f"add {slug2} param to main function"},
        {"summary": "Run tests to verify changes", "tool": "Bash",
         "cmd": f"pytest {tests} -v", "output_hint": "all pass"},
        {"summary": "Check for linting issues", "tool": "Bash",
         "cmd": f"ruff check {src}/", "output_hint": "clean"},
        {"summary": f"Update {slug2} helper module", "tool": "Edit",
         "file": f"{src}/{slug2}.py", "diff_hint": "import and call new function"},
        {"summary": "Run full test suite", "tool": "Bash",
         "cmd": "pytest -x --tb=short", "output_hint": "all pass"},
    ]
    return {
        "project_summary": f"Implement {topic} in the {slug} module",
        "files": files,
        "plan_steps": plan_steps,
        "functions": [f"handle_{slug}", f"validate_{slug}", f"_check_{slug2}", "refresh_session"],
        "test_output_summary": f"{passed} passed, {skipped} skipped",
        "files_changed": 2,
        "lines_changed": random.randint(25, 65),
    }


def get_seed(topic: str, offline: bool = False) -> dict:
    if offline:
        with console.status("[dim]Initializing session (offline)...[/dim]", spinner="dots"):
            _sleep(random.uniform(0.4, 0.9))
        return _local_seed(topic)

    client = anthropic.Anthropic()
    with console.status("[dim]Initializing session...[/dim]", spinner="dots"):
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=800,
            messages=[{"role": "user", "content": SEED_PROMPT.format(topic=topic)}],
        )
    text = msg.content[0].text.strip()
    # Strip any accidental markdown fences
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)


# ── Token counter state ────────────────────────────────────────────────────────

class TokenCounter:
    def __init__(self):
        self.input = random.randint(2000, 5000)
        self.output = random.randint(400, 1200)

    def tick(self):
        self.input += random.randint(80, 400)
        self.output += random.randint(20, 100)

    def render(self) -> str:
        return f"[dim]↑ {self.input:,}  ↓ {self.output:,} tokens[/dim]"


# ── Visual helpers ─────────────────────────────────────────────────────────────

def think(seconds: float, label: str = "Thinking...", tokens: TokenCounter = None):
    """Show spinner for given duration, ticking tokens."""
    steps = max(1, int(seconds / 0.15))
    with Live(console=console, refresh_per_second=12) as live:
        for _ in range(steps):
            suffix = f"  {tokens.render()}" if tokens else ""
            live.update(Text(f"⠸ {label}{suffix}", style="dim cyan"))
            if tokens:
                tokens.tick()
            _sleep(0.15)


def type_text(text: str, delay_range=(0.015, 0.025)):
    """Print text character by character."""
    for ch in text:
        console.print(ch, end="", highlight=False)
        _sleep(random.uniform(*delay_range))
    console.print()  # newline


def show_plan(seed: dict):
    """Phase 2: animate plan writing."""
    console.print()
    console.print("[bold cyan]Claude Code[/bold cyan] [dim]— Plan Mode[/dim]")
    console.print()

    plan_text = f"## Plan: {seed['project_summary']}\n\n"
    for i, step in enumerate(seed["plan_steps"], 1):
        plan_text += f"{i}. {step['summary']}\n"

    # Print panel header
    console.print(Panel("", title="[bold]Plan[/bold]", border_style="cyan", expand=False), end="")
    # Animate the plan content character by character
    console.print("[cyan]┌─ Plan ──────────────────────────────────────────────────────────[/cyan]")
    lines = plan_text.strip().split("\n")
    for line in lines:
        console.print("[cyan]│[/cyan] ", end="")
        for ch in line:
            console.print(ch, end="", highlight=False)
            _sleep(random.uniform(0.012, 0.022))
        console.print()
        _sleep(random.uniform(0.05, 0.15))
    console.print("[cyan]└────────────────────────────────────────────────────────────────[/cyan]")
    console.print()
    _sleep(0.8)

    # Auto-approve
    console.print("[dim]▶ Execute plan?[/dim] ", end="")
    _sleep(0.5)
    console.print("[bold green][y] Approved[/bold green]")
    console.print()
    _sleep(0.4)


# ── Tool renderers ─────────────────────────────────────────────────────────────

def render_read(step: dict, seed: dict):
    path = step.get("file", "src/unknown.py")
    lines = step.get("lines", random.randint(80, 300))
    console.print(f"[bold green]●[/bold green] [bold]Read[/bold] [cyan]{path}[/cyan] [dim]({lines} lines)[/dim]")
    # Show a few fake lines as a preview
    lang = "python"
    funcs = seed.get("functions", ["main", "helper"])
    preview_lines = []
    for fn in funcs[:2]:
        preview_lines.append(f"def {fn}(self, ctx):")
        preview_lines.append(f"    # ... {random.randint(10, 30)} lines ...")
    preview = "\n".join(preview_lines)
    console.print(Syntax(preview, lang, theme="monokai", line_numbers=False,
                         background_color="default", indent_guides=False))
    console.print()


def render_glob(step: dict):
    pattern = step.get("pattern", "src/**/*.py")
    results = step.get("results", ["src/main.py", "src/utils.py"])
    console.print(f"[bold green]●[/bold green] [bold]Glob[/bold] [cyan]{pattern}[/cyan]")
    for r in results:
        console.print(f"  [dim]{r}[/dim]")
    console.print(f"  [dim]({len(results)} files)[/dim]")
    console.print()


def _make_diff(step: dict, seed: dict) -> tuple[str, str]:
    """Return (old_code, new_code) based on diff_hint."""
    hint = step.get("diff_hint", "update function")
    path = step.get("file", "src/module.py")
    funcs = seed.get("functions", ["process", "validate"])
    fn = funcs[0] if funcs else "process"

    hint_lower = hint.lower()
    if "import" in hint_lower:
        removed = "# no import"
        added = f"import logging\nfrom typing import Optional"
    elif "param" in hint_lower or "ctx" in hint_lower or "arg" in hint_lower:
        removed = f"def {fn}(self, data):\n    return self._run(data)"
        added = f"def {fn}(self, data, ctx=None):\n    if ctx:\n        self._bind_context(ctx)\n    return self._run(data)"
    elif "extract" in hint_lower or "helper" in hint_lower:
        removed = (f"def {fn}(self, payload):\n"
                   f"    result = self._validate(payload)\n"
                   f"    if not result.ok:\n"
                   f"        raise ValueError(result.error)\n"
                   f"    return self._process(result.data)")
        fn2 = funcs[1] if len(funcs) > 1 else "validate_and_raise"
        added = (f"def {fn2}(self, payload):\n"
                 f"    result = self._validate(payload)\n"
                 f"    if not result.ok:\n"
                 f"        raise ValueError(result.error)\n"
                 f"    return result.data\n\n"
                 f"def {fn}(self, payload):\n"
                 f"    data = self.{fn2}(payload)\n"
                 f"    return self._process(data)")
    elif "call" in hint_lower or "invoke" in hint_lower:
        fn2 = funcs[1] if len(funcs) > 1 else "helper"
        removed = f"result = self._process(data)"
        added = f"result = self.{fn2}(data)\nresult = self._process(result)"
    else:
        removed = (f"def {fn}(self):\n    pass")
        added = (f"def {fn}(self):\n    self._setup()\n    return self._execute()")

    return removed, added


def render_edit(step: dict, seed: dict):
    path = step.get("file", "src/unknown.py")
    console.print(f"[bold green]●[/bold green] [bold]Edit[/bold] [cyan]{path}[/cyan]")

    removed, added = _make_diff(step, seed)

    diff_lines = []
    for line in removed.split("\n"):
        diff_lines.append(f"- {line}")
    for line in added.split("\n"):
        diff_lines.append(f"+ {line}")
    diff_text = "\n".join(diff_lines)

    # Color the diff manually
    colored = Text()
    for line in diff_lines:
        if line.startswith("- "):
            colored.append(line + "\n", style="red")
        elif line.startswith("+ "):
            colored.append(line + "\n", style="green")
        else:
            colored.append(line + "\n")

    console.print(Panel(colored, border_style="dim", expand=False, padding=(0, 1)))
    console.print()


def _fake_pytest_output(summary: str, cmd: str) -> str:
    passed = random.randint(8, 24)
    skipped = random.randint(0, 3)
    lines = [
        "========================= test session starts ==========================",
        f"platform linux -- Python 3.11.{random.randint(0,9)}, pytest-7.4.{random.randint(0,3)}",
        "collecting ... ",
        f"collected {passed + skipped} items",
        "",
    ]
    test_files = ["tests/test_core.py", "tests/test_utils.py", "tests/test_integration.py"]
    for tf in random.sample(test_files, k=min(2, len(test_files))):
        dots = "." * random.randint(3, 8)
        lines.append(f"{tf} {dots}")
    lines += [
        "",
        f"{'=' * 20} {passed} passed, {skipped} skipped in {random.uniform(0.8, 3.2):.2f}s {'=' * 20}",
    ]
    return "\n".join(lines)


def _fake_ruff_output(cmd: str) -> str:
    if random.random() < 0.85:
        return "All checks passed."
    return f"src/module.py:42:5: E501 Line too long ({random.randint(82,100)} > 79 characters)"


def _fake_git_output(cmd: str) -> str:
    return ("On branch main\nYour branch is up to date with 'origin/main'.\n\n"
            "Changes not staged for commit:\n"
            f"  modified:   src/handler.py\n"
            f"  modified:   src/utils.py")


def render_bash(step: dict, seed: dict, tokens: TokenCounter):
    cmd = step.get("cmd", "echo done")
    console.print(f"[bold green]●[/bold green] [bold]Bash[/bold]")
    console.print(Panel(f"[bold white]{cmd}[/bold white]", border_style="dim", expand=False, padding=(0, 1)))

    # Auto-approve
    console.print("[dim]  Allow bash command?[/dim] ", end="")
    _sleep(0.5)
    console.print("[bold green][y] Approved[/bold green]")

    # Simulate running
    duration = _uniform(2.0, 5.5)
    steps_run = max(1, int(duration / (0.2 * SPEED_MULT)))
    with Live(console=console, refresh_per_second=8) as live:
        for i in range(steps_run):
            bar_len = 20
            filled = int(bar_len * i / steps_run)
            bar = "█" * filled + "░" * (bar_len - filled)
            live.update(Text(f"  [dim][{bar}] running...[/dim]"))
            tokens.tick()
            _sleep(0.2)

    # Fake output
    cmd_lower = cmd.lower()
    if "pytest" in cmd_lower:
        output = _fake_pytest_output(seed.get("test_output_summary", "10 passed"), cmd)
    elif "ruff" in cmd_lower or "flake8" in cmd_lower or "lint" in cmd_lower:
        output = _fake_ruff_output(cmd)
    elif "git" in cmd_lower:
        output = _fake_git_output(cmd)
    elif "pip" in cmd_lower or "install" in cmd_lower:
        pkg = cmd.split()[-1] if cmd.split() else "package"
        output = f"Requirement already satisfied: {pkg}"
    else:
        output = f"Done. ({random.uniform(0.1, 1.2):.2f}s)"

    console.print(Panel(
        Syntax(output, "text", theme="monokai", background_color="default"),
        border_style="dim", expand=False, padding=(0, 1)
    ))
    console.print()


# ── Main session loop ──────────────────────────────────────────────────────────

def run_session(topic: str, offline: bool = False):
    console.rule(f"[bold cyan]New Session[/bold cyan]  [dim]{topic}[/dim]")
    console.print()

    # Phase 1: Seed
    seed = get_seed(topic, offline=offline)
    tokens = TokenCounter()

    # Header
    console.print(f"[bold]Claude Code[/bold]  [dim]claude-sonnet-4-6[/dim]")
    console.print(f"[dim]cwd: ~/projects/{seed['files'][0]['path'].split('/')[0] if seed['files'] else 'app'}[/dim]")
    console.print()
    console.print(f"[bold white]{seed['project_summary']}[/bold white]")
    console.print()

    # Phase 2: Planning
    think(_uniform(1.5, 2.5), "Analyzing codebase...", tokens)
    console.print()
    show_plan(seed)

    # Phase 3: Execution
    for i, step in enumerate(seed["plan_steps"]):
        # Occasional reconsider (10%)
        if i > 0 and random.random() < 0.10:
            think(_uniform(2.0, 4.0), "Hmm, let me reconsider...", tokens)
            console.print()

        # Step label
        console.print(f"[dim]Step {i+1}/{len(seed['plan_steps'])}[/dim]  {tokens.render()}")

        think(_uniform(1.0, 3.5), "Thinking...", tokens)
        console.print()

        tool = step.get("tool", "Read")
        if tool == "Read":
            render_read(step, seed)
        elif tool == "Glob":
            render_glob(step)
        elif tool == "Edit":
            render_edit(step, seed)
        elif tool == "Bash":
            render_bash(step, seed, tokens)
        else:
            # Fallback generic
            console.print(f"[bold green]●[/bold green] [bold]{tool}[/bold]  [dim]{step.get('summary', '')}[/dim]")
            console.print()

        # Token tick after each step
        tokens.tick()

    # Phase 4: Summary
    console.print()
    files_changed = seed.get("files_changed", random.randint(2, 5))
    lines_changed = seed.get("lines_changed", random.randint(20, 80))
    test_summary = seed.get("test_output_summary", f"{random.randint(8,24)} passed")
    console.print(Panel(
        f"[bold green]✓ Done[/bold green]  Updated [bold]{files_changed} files[/bold] · "
        f"[bold]{lines_changed} lines changed[/bold] · "
        f"[bold]{test_summary}[/bold]\n"
        f"{tokens.render()}",
        border_style="green",
        expand=False,
        padding=(0, 2),
    ))
    console.print()


def main():
    global SPEED_MULT
    args = sys.argv[1:]
    offline = "--offline" in args
    slow = "--slow" in args
    args = [a for a in args if a not in ("--offline", "--slow")]
    if slow:
        SPEED_MULT = 3.0

    topic = " ".join(args).strip() if args else random.choice(DEFAULT_TOPICS)
    fixed_topic = bool(args)

    # Check for API key unless running offline
    if not offline and not os.environ.get("ANTHROPIC_API_KEY"):
        console.print()
        console.print("[bold red]Error:[/bold red] ANTHROPIC_API_KEY is not set.")
        console.print()
        console.print("Set it with:  [bold]export ANTHROPIC_API_KEY=sk-ant-...[/bold]")
        console.print("Or run without an API key:  [bold]python vibe.py --offline \"your topic\"[/bold]")
        console.print()
        sys.exit(1)

    console.print()
    console.print("[bold cyan]vibe-coder[/bold cyan]  [dim]Claude Code simulator[/dim]")
    console.print(f"[dim]Topic: {topic}[/dim]")
    if offline:
        console.print("[dim]Mode: offline (no API calls)[/dim]")
    if slow:
        console.print("[dim]Mode: slow (10x timing)[/dim]")
    console.print("[dim]Press Ctrl+C to exit[/dim]")
    console.print()

    session_count = 0
    try:
        while True:
            session_count += 1
            run_session(topic, offline=offline)
            if not fixed_topic:
                topic = random.choice(DEFAULT_TOPICS)
            console.print(f"[dim]Session {session_count} complete. Starting next session in 5s...[/dim]")
            _sleep(5)
    except KeyboardInterrupt:
        console.print()
        console.print(f"[bold cyan]vibe-coder[/bold cyan] [dim]— {session_count} session(s) completed. Goodbye.[/dim]")
        console.print()


if __name__ == "__main__":
    main()
