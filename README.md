# just-vibin

A terminal simulator that convincingly fakes a Claude Code AI coding session. Designed to wind up skeptical coworkers who think you're just vibing while the AI does all the work — because now you actually are.

Looks completely real: spinning "Thinking..." indicators, file reads with code previews, syntax-highlighted diffs, bash command approvals, a planning phase, live token counters, and a tidy summary at the end. Loops forever until you close it.

![Python](https://img.shields.io/badge/python-3.8+-blue) ![License](https://img.shields.io/badge/license-MIT-green)

---

## How it works

Each session runs in four phases:

1. **Seed** — generates a session scaffold using the local vocabulary engine. No API key required. Pass `--api` to use a real `claude-haiku` call instead for more varied, topic-specific output.

2. **Plan** — types out a numbered plan character-by-character into a styled panel, then auto-approves it after a short pause.

3. **Execution** — steps through the plan, rendering each tool call realistically:
   - `Read` — shows file path, line count, and a contextual code preview (dataclass, service class, async handler, repository, exception hierarchy — picked randomly)
   - `Glob` — lists matched files
   - `Edit` — shows a red/green diff in a panel, drawn from 9 distinct patterns (add parameter, extract helper, add logging, guard clause, enum constants, async conversion, cache decorator, typed schema, dependency injection)
   - `Bash` — shows the command, auto-approves it, runs a progress bar, then prints contextually appropriate output (pytest results with real file names, ruff/mypy/pylint errors, git status with actual modified files, alembic migrations, docker compose, etc.)

   A spinner with a live token counter runs between each step. The spinner message rotates through 10 different phrases. 10% of the time it pauses to "reconsider" with one of 6 different hesitation phrases.

4. **Summary** — prints a green completion panel with files changed, lines changed, and test results, then waits 5 seconds and loops with a fresh session.

---

## Dependencies

```
rich       # terminal UI: spinners, panels, syntax highlighting, live displays
anthropic  # Haiku API call to seed each session (optional with --offline)
```

Install with:

```bash
pip install -r requirements.txt
```

---

## Usage

```bash
python vibe.py [--api] [--slow] [topic]
```

**Offline is the default.** No API key needed to run. Pass `--api` to seed sessions with a real Haiku call instead.

### Basic

```bash
python vibe.py "add oauth2 login"
python vibe.py "refactor auth module to support MFA"
python vibe.py "migrate database schema to multi-tenancy"
python vibe.py "add stripe billing webhooks"
```

After the first session, the topic is automatically remixed from your original words — e.g. `"add oauth2 login"` might become `"scaffold refresh tokens handler"` or `"normalise oauth2 flow"` — so each loop looks like a fresh task.

### API mode

Uses a real `claude-haiku` call to generate a richer seed tailored to your topic. Requires `ANTHROPIC_API_KEY` to be set.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python vibe.py --api "add oauth2 login"
```

If `--api` is passed without a key set, the script will tell you and exit.

### Slow mode

3x all timing delays — good for leaving on a second monitor to really commit to the bit.

```bash
python vibe.py --slow "extract payment service into microservice"
python vibe.py --slow --api "add redis caching layer"
```

### Random topic (no argument)

Picks a random topic each session from a built-in list and rotates through them.

```bash
python vibe.py
python vibe.py --slow
```

### Exit

`Ctrl+C` — exits cleanly and prints a session count.

---

## Vocabulary engine

`vocab.py` is a dictionary that drives session variety without any API calls. It's used in both offline mode and as a fallback if the API response is malformed. It contains:

- **24 action verbs** — refactor, instrument, decompose, harden, etc.
- **25 domain names** — auth, billing, cache, queue, telemetry, feature_flag, etc.
- **16 module suffixes** — handler, repository, dispatcher, adapter, registry, etc.
- **5 file structure templates** — `src/`, `app/`, `lib/`, `services/` layouts
- **Function name generator** — combines prefix + domain + suffix pools for unique names each session
- **20 diff hints** → 9 diff patterns — add parameter, extract helper, add logging, guard clause, enum constants, async conversion, cache decorator, typed schema, dependency injection
- **Bash command templates** — across test, lint, git, and misc categories
- **5 code snippet templates** — dataclass model, service class, async handler, exception hierarchy, repository pattern
- **Lint error pool** — 7 real error codes (E501, F401, B006, C901, etc.) with realistic line numbers
- **10 thinking phrases + 6 reconsider phrases** — rotated randomly during spinner phases

---

## Cost

One Haiku API call per session loop. The response budget is set to **1,200 tokens** to handle complex topics without truncation.

**Default (offline): $0.** No API calls are made.

When running with `--api`, one Haiku call is made per session loop. At current Anthropic Haiku pricing (~$0.80/MTok input, ~$4.00/MTok output):

| | Tokens | Cost |
|---|---|---|
| Input (prompt) | ~250 | ~$0.0002 |
| Output (seed JSON) | ~900 | ~$0.0036 |
| **Per session** | | **~$0.004** |

A full hour of `--api` looping (assuming ~2 min/session) costs around **$0.12**.
