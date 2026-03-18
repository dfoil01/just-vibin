#!/usr/bin/env python3
"""vibe-coder: Terminal Claude Code simulator. Fakes a convincing AI coding session."""

import sys
import time
import random
import json
import os

import anthropic
import vocab
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
    stop_words = {"add","the","a","an","to","for","with","and","or","of","in","on",
                  "implement","refactor","migrate","fix","update","create","use","using"}
    words = [w.lower().strip(".,") for w in topic.split()]
    domain_words = [w for w in words if w not in stop_words and len(w) > 2]

    # Pick domain — prefer known domains, fall back to topic words
    domain = next((w for w in domain_words if w in vocab.DOMAINS), None)
    if domain is None:
        domain = domain_words[0] if domain_words else random.choice(vocab.DOMAINS)
    module = random.choice(vocab.MODULE_SUFFIXES)

    # File structure
    src_tmpl, test_dir, file_names = random.choice(vocab.FILE_STRUCTURES)
    src = src_tmpl.format(domain=domain)
    main_file = file_names[0].format(module=module, domain=domain)
    support_files = [f.format(module=module, domain=domain) for f in file_names[1:]]
    tests = f"{test_dir}/test_{domain}.py"

    files = [
        {"path": f"{src}/{main_file}", "language": "python",
         "lines": random.randint(140, 320), "purpose": f"main {domain} {module}"},
    ]
    for sf in support_files:
        files.append({"path": f"{src}/{sf}", "language": "python",
                      "lines": random.randint(40, 120), "purpose": sf.replace(".py","").replace("_"," ")})
    files.append({"path": tests, "language": "python",
                  "lines": random.randint(80, 180), "purpose": "test suite"})

    functions = vocab.random_functions(domain, n=4)
    diff_hints = random.sample(vocab.DIFF_HINTS, k=2)
    action = random.choice(vocab.ACTIONS)
    passed = random.randint(8, 28)
    skipped = random.randint(0, 3)

    core_steps = [
        {"summary": f"{random.choice(vocab.PLAN_VERBS)} existing {domain} {module}",
         "tool": "Read", "file": f"{src}/{main_file}", "lines": files[0]["lines"]},
        {"summary": f"Search for {domain} patterns across codebase",
         "tool": "Glob", "pattern": f"{src}/**/*.py",
         "results": [f["path"] for f in files[:3]]},
        {"summary": f"{action.capitalize()} {main_file} — {diff_hints[0]}",
         "tool": "Edit", "file": f"{src}/{main_file}", "diff_hint": diff_hints[0]},
        {"summary": "Run targeted tests",
         "tool": "Bash",
         "cmd": vocab.random_bash_cmd(src, tests, domain, module),
         "output_hint": "all pass"},
        {"summary": "Check types and linting",
         "tool": "Bash",
         "cmd": vocab.random_bash_cmd(src, tests, domain, module),
         "output_hint": "clean"},
        {"summary": f"Update {support_files[0]} — {diff_hints[1]}",
         "tool": "Edit", "file": f"{src}/{support_files[0]}", "diff_hint": diff_hints[1]},
        {"summary": "Run full test suite",
         "tool": "Bash", "cmd": "pytest -x --tb=short", "output_hint": "all pass"},
    ]

    # Vary total steps: pad core with extras up to a random target (4–10)
    target = random.randint(4, 10)
    if target > len(core_steps):
        extras = vocab.extra_steps(src, tests, domain, module, files)
        random.shuffle(extras)
        core_steps += extras[:target - len(core_steps)]
    else:
        core_steps = core_steps[:target]

    # Attach subtasks to ~10% of steps (2–5 subtasks each)
    sub_pool = vocab.subtask_steps(src, tests, domain, module)
    for step in core_steps:
        if random.random() < 0.10:
            n = random.randint(2, 5)
            random.shuffle(sub_pool)
            step["subtasks"] = [dict(s) for s in sub_pool[:n]]

    plan_steps = core_steps
    return {
        "project_summary": vocab.random_project_summary(action, domain, topic),
        "files": files,
        "plan_steps": plan_steps,
        "functions": functions,
        "test_output_summary": f"{passed} passed, {skipped} skipped",
        "files_changed": random.randint(2, 4),
        "lines_changed": random.randint(25, 80),
        "_src": src,
        "_domain": domain,
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
            max_tokens=1200,
            messages=[{"role": "user", "content": SEED_PROMPT.format(topic=topic)}],
        )
    text = msg.content[0].text.strip()
    # Strip any accidental markdown fences
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        console.print("[dim]Warning: API response malformed, falling back to local seed.[/dim]")
        return _local_seed(topic)


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
        for j, sub in enumerate(step.get("subtasks", []), 1):
            plan_text += f"   {i}.{j}. {sub['summary']}\n"

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
    funcs = seed.get("functions", ["process", "validate"])
    domain = seed.get("_domain", path.split("/")[-2] if "/" in path else "core")
    fn = funcs[0] if funcs else "process"
    fn2 = funcs[1] if len(funcs) > 1 else "helper"
    preview = vocab.random_snippet(domain, fn, fn2, random.randint(10, 40))
    console.print(Syntax(preview, "python", theme="monokai", line_numbers=False,
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
    hint = step.get("diff_hint", random.choice(vocab.DIFF_HINTS))
    funcs = seed.get("functions", ["process", "validate"])
    domain = seed.get("_domain", "core")
    fn = funcs[0] if funcs else "process"
    fn2 = funcs[1] if len(funcs) > 1 else "validate_and_raise"
    Domain = domain.replace("_", " ").title().replace(" ", "")

    hint_lower = hint.lower()
    if "import" in hint_lower or "dependency" in hint_lower:
        removed = "# stdlib only"
        added = f"import logging\nfrom typing import Optional\nfrom .models import {Domain}Schema"
    elif "param" in hint_lower or "ctx" in hint_lower or "arg" in hint_lower or "keyword" in hint_lower:
        removed = f"def {fn}(self, data):\n    return self._run(data)"
        added = (f"def {fn}(self, data, *, ctx: Optional[Context] = None):\n"
                 f"    if ctx:\n        self._bind_context(ctx)\n"
                 f"    return self._run(data)")
    elif "extract" in hint_lower or "helper" in hint_lower or "split" in hint_lower or "two step" in hint_lower:
        removed = (f"def {fn}(self, payload):\n"
                   f"    result = self._validate(payload)\n"
                   f"    if not result.ok:\n"
                   f"        raise {Domain}Error(result.error)\n"
                   f"    return self._process(result.data)")
        added = (f"def {fn2}(self, payload):\n"
                 f"    result = self._validate(payload)\n"
                 f"    if not result.ok:\n"
                 f"        raise {Domain}Error(result.error)\n"
                 f"    return result.data\n\n"
                 f"def {fn}(self, payload):\n"
                 f"    data = self.{fn2}(payload)\n"
                 f"    return self._process(data)")
    elif "cache" in hint_lower or "decorator" in hint_lower:
        removed = f"def {fn}(self, key: str) -> Optional[{Domain}]:"
        added = (f"@cached(ttl=300)\n"
                 f"def {fn}(self, key: str) -> Optional[{Domain}]:")
    elif "logging" in hint_lower or "log" in hint_lower:
        removed = (f"def {fn}(self, payload):\n"
                   f"    return self._process(payload)")
        added = (f"def {fn}(self, payload):\n"
                 f"    logger.info(\"processing %s\", payload.id)\n"
                 f"    result = self._process(payload)\n"
                 f"    logger.debug(\"result: %s\", result)\n"
                 f"    return result")
    elif "guard" in hint_lower or "early" in hint_lower or "return" in hint_lower:
        removed = (f"def {fn}(self, item):\n"
                   f"    if item is not None:\n"
                   f"        if item.is_active:\n"
                   f"            return self._process(item)\n"
                   f"    return None")
        added = (f"def {fn}(self, item):\n"
                 f"    if item is None or not item.is_active:\n"
                 f"        return None\n"
                 f"    return self._process(item)")
    elif "enum" in hint_lower or "constant" in hint_lower or "magic" in hint_lower:
        removed = (f"if status == \"pending\":\n"
                   f"    ...\nelif status == \"complete\":\n"
                   f"    ...")
        added = (f"class {Domain}Status(str, Enum):\n"
                 f"    PENDING = \"pending\"\n"
                 f"    COMPLETE = \"complete\"\n\n"
                 f"if status == {Domain}Status.PENDING:\n"
                 f"    ...\nelif status == {Domain}Status.COMPLETE:\n"
                 f"    ...")
    elif "async" in hint_lower or "await" in hint_lower:
        removed = (f"def {fn}(self, id: str) -> {Domain}:\n"
                   f"    return self.db.query({Domain}).filter_by(id=id).first()")
        added = (f"async def {fn}(self, id: str) -> {Domain}:\n"
                 f"    return await self.db.get({Domain}, id)")
    elif "dataclass" in hint_lower or "typed" in hint_lower or "schema" in hint_lower:
        removed = f"def {fn}(self, data: dict) -> dict:"
        added = (f"def {fn}(self, data: {Domain}Request) -> {Domain}Response:")
    else:
        removed = f"def {fn}(self):\n    pass"
        added = (f"def {fn}(self):\n"
                 f"    self._setup()\n"
                 f"    result = self._execute()\n"
                 f"    return result")

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


def _fake_pytest_output(summary: str, cmd: str, seed: dict) -> str:
    passed = random.randint(8, 28)
    skipped = random.randint(0, 3)
    failed = 1 if random.random() < 0.05 else 0  # rare flap
    src = seed.get("_src", "src/core")
    domain = seed.get("_domain", "core")
    lines = [
        "========================= test session starts ==========================",
        f"platform darwin -- Python 3.11.{random.randint(0,9)}, pytest-7.4.{random.randint(0,3)}, pluggy-1.3.0",
        f"rootdir: /home/user/project",
        "collecting ... ",
        f"collected {passed + skipped + failed} items",
        "",
    ]
    for tf in vocab.random_test_file_names(src):
        dots = "." * random.randint(3, 10)
        if failed and tf == lines[-1] if lines else False:
            dots = dots[:-1] + "F"
        lines.append(f"{tf} {dots}")
    result_parts = [f"{passed} passed"]
    if skipped:
        result_parts.append(f"{skipped} skipped")
    if failed:
        result_parts.append(f"{failed} failed")
    result_str = ", ".join(result_parts)
    lines += [
        "",
        f"{'=' * 20} {result_str} in {random.uniform(0.4, 4.5):.2f}s {'=' * 20}",
    ]
    return "\n".join(lines)


def _fake_ruff_output(cmd: str, seed: dict) -> str:
    src = seed.get("_src", "src/core")
    funcs = seed.get("functions", ["process"])
    fn = funcs[0]
    if random.random() < 0.82:
        return "All checks passed."
    n_errors = random.randint(1, 3)
    return "\n".join(vocab.random_lint_error(src, fn) for _ in range(n_errors))


def _fake_git_output(cmd: str, seed: dict) -> str:
    files = seed.get("files", [])
    modified = [f["path"] for f in files[:2]]
    mod_lines = "\n".join(f"  modified:   {p}" for p in modified)
    return (f"On branch main\nYour branch is up to date with 'origin/main'.\n\n"
            f"Changes not staged for commit:\n{mod_lines}")


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
    if "pytest" in cmd_lower or "python -m pytest" in cmd_lower:
        output = _fake_pytest_output(seed.get("test_output_summary", "10 passed"), cmd, seed)
    elif "ruff" in cmd_lower or "flake8" in cmd_lower or "mypy" in cmd_lower or "pylint" in cmd_lower:
        output = _fake_ruff_output(cmd, seed)
    elif "git" in cmd_lower:
        output = _fake_git_output(cmd, seed)
    elif "pip" in cmd_lower or "install" in cmd_lower:
        pkg = cmd.split()[-1] if cmd.split() else "package"
        output = f"Requirement already satisfied: {pkg}"
    elif "alembic" in cmd_lower:
        output = f"INFO  [alembic.runtime.migration] Running upgrade abc123 -> def456, add_{seed.get('_domain','core')}_columns"
    elif "docker" in cmd_lower:
        output = "Container db started.\nContainer redis started."
    elif "manage.py" in cmd_lower:
        output = "System check identified no issues (0 silenced)."
    else:
        output = f"Done. ({random.uniform(0.1, 1.8):.2f}s)"

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
    think(_uniform(1.5, 2.5), random.choice(vocab.THINKING_PHRASES), tokens)
    console.print()
    show_plan(seed)

    def execute_step(step: dict, label: str):
        think(_uniform(1.0, 3.5), random.choice(vocab.THINKING_PHRASES), tokens)
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
            console.print(f"[bold green]●[/bold green] [bold]{tool}[/bold]  [dim]{step.get('summary', '')}[/dim]")
            console.print()
        tokens.tick()

    # Phase 3: Execution
    total = len(seed["plan_steps"])
    for i, step in enumerate(seed["plan_steps"]):
        # Occasional reconsider (10%)
        if i > 0 and random.random() < 0.10:
            think(_uniform(2.0, 4.0), random.choice(vocab.RECONSIDER_PHRASES), tokens)
            console.print()

        console.print(f"[dim]Step {i+1}/{total}[/dim]  {tokens.render()}")
        execute_step(step, f"{i+1}")

        # Subtasks
        for j, sub in enumerate(step.get("subtasks", []), 1):
            console.print(f"[dim]  Step {i+1}.{j}[/dim]  {tokens.render()}")
            execute_step(sub, f"{i+1}.{j}")

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


def _remix_topic(original: str) -> str:
    """Recombine words from the original topic with vocab to produce a fresh variant."""
    stop_words = {"add","the","a","an","to","for","with","and","or","of","in","on",
                  "implement","refactor","migrate","fix","update","create","use","using"}
    user_words = [w.lower().strip(".,") for w in original.split() if w.lower() not in stop_words and len(w) > 2]
    if not user_words:
        user_words = [random.choice(vocab.DOMAINS)]

    action = random.choice(vocab.ACTIONS)
    # Keep 1-3 words from the original topic
    kept = random.sample(user_words, k=min(random.randint(1, 3), len(user_words)))
    # Optionally splice in a vocab domain or module suffix for variety
    if random.random() < 0.5:
        kept.append(random.choice(vocab.MODULE_SUFFIXES))
    return f"{action} {' '.join(kept)}"


def main():
    global SPEED_MULT
    args = sys.argv[1:]
    use_api = "--api" in args
    slow = "--slow" in args
    args = [a for a in args if a not in ("--api", "--slow", "--offline")]
    if slow:
        SPEED_MULT = 3.0

    topic = " ".join(args).strip() if args else random.choice(DEFAULT_TOPICS)
    user_supplied_topic = bool(args)
    offline = not use_api

    # Check for API key only when --api is explicitly requested
    if use_api and not os.environ.get("ANTHROPIC_API_KEY"):
        console.print()
        console.print("[bold red]Error:[/bold red] ANTHROPIC_API_KEY is not set.")
        console.print()
        console.print("Set it with:  [bold]export ANTHROPIC_API_KEY=sk-ant-...[/bold]")
        console.print("Or drop --api to run fully offline (default).")
        console.print()
        sys.exit(1)

    console.print()
    console.print("[bold cyan]vibe-coder[/bold cyan]  [dim]Claude Code simulator[/dim]")
    console.print(f"[dim]Topic: {topic}[/dim]")
    console.print(f"[dim]Mode: {'api (claude-haiku)' if use_api else 'offline'}{'  · slow (3x)' if slow else ''}[/dim]")
    console.print("[dim]Press Ctrl+C to exit[/dim]")
    console.print()

    session_count = 0
    try:
        while True:
            session_count += 1
            run_session(topic, offline=offline)
            # After first session: remix the topic from user words (or rotate defaults)
            if user_supplied_topic:
                topic = _remix_topic(topic if session_count == 1 else topic)
            else:
                topic = random.choice(DEFAULT_TOPICS)
            console.print(f"[dim]Session {session_count} complete. Next: \"{topic}\" — starting in 5s...[/dim]")
            _sleep(5)
    except KeyboardInterrupt:
        console.print()
        console.print(f"[bold cyan]vibe-coder[/bold cyan] [dim]— {session_count} session(s) completed. Goodbye.[/dim]")
        console.print()


if __name__ == "__main__":
    main()
