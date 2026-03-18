"""Vocabulary bank for vibe-coder session variety."""

import random

# ── Actions / verbs ────────────────────────────────────────────────────────────

ACTIONS = [
    "refactor", "implement", "migrate", "extract", "optimize", "add", "fix",
    "integrate", "extend", "replace", "scaffold", "wire up", "harden",
    "decompose", "abstract", "consolidate", "deprecate", "instrument",
    "backfill", "expose", "stub out", "plumb", "decouple", "normalise",
]

PLAN_VERBS = [
    "Read", "Inspect", "Review", "Examine", "Check", "Analyse",
]

THINKING_PHRASES = [
    "Thinking...",
    "Analysing dependencies...",
    "Checking for edge cases...",
    "Reasoning about types...",
    "Reading context...",
    "Considering approach...",
    "Planning next step...",
    "Cross-referencing...",
    "Tracing call stack...",
    "Reviewing recent changes...",
]

RECONSIDER_PHRASES = [
    "Hmm, let me reconsider...",
    "Wait, let me double-check that...",
    "Actually, let me re-read this...",
    "Hold on, there's a subtlety here...",
    "Let me trace through this again...",
    "Something feels off, re-examining...",
]

# ── Domains / modules ──────────────────────────────────────────────────────────

DOMAINS = [
    "auth", "billing", "cache", "queue", "webhook", "notification",
    "report", "export", "search", "analytics", "ingestion", "pipeline",
    "scheduler", "worker", "gateway", "session", "token", "rate_limit",
    "audit", "config", "feature_flag", "email", "storage", "metrics",
    "telemetry", "profile", "subscription", "inventory", "order",
]

MODULE_SUFFIXES = [
    "handler", "service", "manager", "client", "processor", "dispatcher",
    "resolver", "controller", "middleware", "validator", "serializer",
    "repository", "adapter", "provider", "registry", "factory",
]

# ── File path templates ────────────────────────────────────────────────────────

FILE_STRUCTURES = [
    # (src_dir, test_dir, file_names)
    ("src/{domain}", "tests", ["{module}.py", "models.py", "utils.py", "exceptions.py"]),
    ("app/{domain}", "tests/{domain}", ["{module}.py", "schemas.py", "deps.py", "routes.py"]),
    ("{domain}", "tests", ["{module}.py", "types.py", "helpers.py", "constants.py"]),
    ("lib/{domain}", "spec", ["{module}.py", "base.py", "mixins.py", "signals.py"]),
    ("services/{domain}", "tests/unit", ["{module}.py", "models.py", "tasks.py", "serializers.py"]),
]

# ── Function name patterns ────────────────────────────────────────────────────

FUNCTION_PREFIXES = [
    "handle", "process", "validate", "build", "fetch", "create",
    "update", "delete", "parse", "format", "check", "verify",
    "dispatch", "resolve", "emit", "notify", "compute", "aggregate",
    "transform", "enrich", "filter", "hydrate", "flush", "reconcile",
]

FUNCTION_SUFFIXES = [
    "request", "response", "payload", "event", "record", "batch",
    "result", "context", "state", "config", "token", "session",
    "message", "entry", "item", "job", "task", "hook",
]

def random_function_name(domain: str) -> str:
    style = random.random()
    if style < 0.4:
        return f"{random.choice(FUNCTION_PREFIXES)}_{domain}"
    elif style < 0.7:
        return f"{random.choice(FUNCTION_PREFIXES)}_{random.choice(FUNCTION_SUFFIXES)}"
    else:
        return f"_{random.choice(FUNCTION_PREFIXES)}_{domain}"

def random_functions(domain: str, n: int = 4) -> list[str]:
    seen = set()
    result = []
    while len(result) < n:
        fn = random_function_name(domain)
        if fn not in seen:
            seen.add(fn)
            result.append(fn)
    return result

# ── Diff hints ─────────────────────────────────────────────────────────────────

DIFF_HINTS = [
    "add ctx param to main function",
    "extract validation logic into helper",
    "add import for new dependency",
    "replace hardcoded value with config lookup",
    "add retry logic around external call",
    "introduce dataclass for return type",
    "wrap response in typed schema",
    "add logging to critical path",
    "inject dependency via constructor",
    "add early-return guard clause",
    "move side-effect into separate method",
    "replace dict with typed model",
    "add async/await to IO-bound call",
    "add cache decorator to expensive query",
    "split monolithic function into two steps",
    "introduce circuit breaker pattern",
    "add enum for magic string constants",
    "replace positional args with keyword-only",
    "add docstring and type annotations",
    "normalise error handling to use custom exception",
]

# ── Bash command templates ─────────────────────────────────────────────────────

BASH_COMMANDS = {
    "test": [
        "pytest {tests} -v",
        "pytest {tests} -v --tb=short",
        "pytest -x --tb=short",
        "pytest {tests} -v -k 'not slow'",
        "python -m pytest {tests} --cov={src} --cov-report=term-missing",
    ],
    "lint": [
        "ruff check {src}/",
        "ruff check {src}/ --fix",
        "flake8 {src}/ --max-line-length=99",
        "mypy {src}/ --ignore-missing-imports",
        "pylint {src}/ --disable=C0114",
    ],
    "git": [
        "git status",
        "git diff --stat",
        "git log --oneline -10",
        "git stash list",
    ],
    "misc": [
        "python -c \"from {domain} import {module}; print('import OK')\"",
        "pip install -r requirements.txt",
        "python manage.py check",
        "alembic upgrade head",
        "python scripts/seed_db.py --env dev",
        "docker compose up -d db redis",
        "celery -A app worker --loglevel=info --dry-run",
    ],
}

def random_bash_cmd(src: str, tests: str, domain: str, module: str) -> str:
    category = random.choices(
        ["test", "lint", "git", "misc"],
        weights=[50, 25, 10, 15],
    )[0]
    template = random.choice(BASH_COMMANDS[category])
    return template.format(src=src, tests=tests, domain=domain, module=module)

# ── Code snippets for Read previews ───────────────────────────────────────────

SNIPPET_TEMPLATES = [
    # (description, code_template)
    ("dataclass model", """\
@dataclass
class {Domain}Config:
    endpoint: str
    timeout: int = 30
    retries: int = 3
    _client: Optional["{Domain}Client"] = field(default=None, init=False)
"""),
    ("service class", """\
class {Domain}Service:
    def __init__(self, db: Session, cache: Redis):
        self.db = db
        self.cache = cache

    def {fn}(self, payload: {Domain}Schema) -> {Domain}Result:
        # ... {lines} lines ...
        pass
"""),
    ("async handler", """\
async def {fn}(
    request: {Domain}Request,
    ctx: RequestContext = Depends(get_context),
) -> {Domain}Response:
    result = await service.{fn2}(request.data, ctx)
    return {Domain}Response(data=result)
"""),
    ("exception hierarchy", """\
class {Domain}Error(AppError):
    status_code = 400

class {Domain}NotFoundError({Domain}Error):
    status_code = 404

class {Domain}ValidationError({Domain}Error):
    status_code = 422
"""),
    ("repository pattern", """\
class {Domain}Repository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, id: UUID) -> Optional[{Domain}]:
        # ... {lines} lines ...
        pass

    async def list_active(self, limit: int = 100) -> list[{Domain}]:
        pass
"""),
]

def random_snippet(domain: str, fn: str, fn2: str, lines: int) -> str:
    template = random.choice(SNIPPET_TEMPLATES)[1]
    Domain = domain.replace("_", " ").title().replace(" ", "")
    return template.format(Domain=Domain, domain=domain, fn=fn, fn2=fn2, lines=lines)

# ── Pytest output helpers ──────────────────────────────────────────────────────

PYTEST_MARKERS = ["unit", "integration", "slow", "smoke", "regression"]

def random_test_file_names(src_dir: str) -> list[str]:
    base = src_dir.replace("src/", "").replace("app/", "").replace("/", "_")
    options = [
        f"tests/test_{base}.py",
        f"tests/test_{base}_integration.py",
        f"tests/unit/test_{base}.py",
        f"tests/test_{base}_service.py",
    ]
    return random.sample(options, k=min(2, len(options)))

# ── Ruff / lint error pool ────────────────────────────────────────────────────

LINT_ERRORS = [
    ("E501", "Line too long ({n} > 99 characters)"),
    ("F401", "'{mod}' imported but unused"),
    ("W291", "Trailing whitespace"),
    ("E302", "Expected 2 blank lines, found 1"),
    ("B006", "Do not use mutable data structures for argument defaults"),
    ("C901", "'{fn}' is too complex ({n})"),
    ("N802", "Function name '{fn}' should be lowercase"),
]

def random_lint_error(src: str, fn: str) -> str:
    code, msg_template = random.choice(LINT_ERRORS)
    line = random.randint(20, 150)
    col = random.randint(1, 10)
    msg = msg_template.format(
        n=random.randint(82, 120),
        mod=f"{src.split('/')[-1]}.utils",
        fn=fn,
    )
    return f"{src}/{random.choice(['handler', 'utils', 'models'])}.py:{line}:{col}: {code} {msg}"

# ── Summary phrases ───────────────────────────────────────────────────────────

SUMMARY_SUFFIXES = [
    "tests passing",
    "all green",
    "no regressions",
    "coverage +2%",
    "linting clean",
]

def random_summary_suffix() -> str:
    return random.choice(SUMMARY_SUFFIXES)

# ── Project summaries ─────────────────────────────────────────────────────────

SUMMARY_TEMPLATES = [
    "{Action} {domain} module to support {feature}",
    "Implement {feature} in the {domain} service",
    "Refactor {domain} handler for {feature}",
    "Add {feature} to {domain} pipeline",
    "Migrate {domain} to use {feature}",
    "Extract {feature} logic from {domain} into dedicated service",
    "Harden {domain} layer with {feature}",
    "Instrument {domain} with {feature}",
]

def random_project_summary(action: str, domain: str, topic: str) -> str:
    feature_words = [w for w in topic.split() if w.lower() not in
                     ("add","the","a","an","to","for","with","and","or","of","in","on",
                      "implement","refactor","migrate","fix","update","create")]
    feature = " ".join(feature_words[:4]) if feature_words else topic
    template = random.choice(SUMMARY_TEMPLATES)
    return template.format(Action=action.capitalize(), domain=domain, feature=feature)
