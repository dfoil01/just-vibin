# just-vibin

A terminal simulator that convincingly fakes a Claude Code AI coding session. Designed to wind up skeptical coworkers who think you're just vibing while the AI does all the work — because now you actually are.

Looks completely real: spinning "Thinking..." indicators, file reads with code previews, syntax-highlighted diffs, bash command approvals, a planning phase, live token counters, and a tidy summary at the end. Loops forever until you close it.

![Python](https://img.shields.io/badge/python-3.8+-blue) ![License](https://img.shields.io/badge/license-MIT-green)

---

## How it works

Each session runs in four phases:

1. **Seed** — makes a single cheap API call to `claude-haiku` (~$0.0004) to generate a realistic JSON scaffold: file paths, a plan, function names, and test output tailored to your topic. Pass `--offline` to skip this entirely and use a local template generator instead.

2. **Plan** — types out a numbered plan character-by-character into a styled panel, then auto-approves it after a short pause.

3. **Execution** — steps through the plan, rendering each tool call realistically:
   - `Read` — shows file path, line count, and a code preview
   - `Glob` — lists matched files
   - `Edit` — shows a red/green diff in a panel
   - `Bash` — shows the command, auto-approves it, runs a progress bar, then prints fake-but-plausible output (pytest results, ruff linting, git status, etc.)

   A spinner with a live token counter runs between each step. 10% of the time it pauses to "reconsider."

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
python vibe.py [--offline] [--slow] [topic]
```

### Basic

```bash
python vibe.py "add oauth2 login"
python vibe.py "refactor auth module to support MFA"
python vibe.py "migrate database schema to multi-tenancy"
python vibe.py "add stripe billing webhooks"
```

### No API key — offline mode

Generates sessions from local templates. No API calls, no key needed.

```bash
python vibe.py --offline "add rate limiting middleware"
```

### Slow mode

10x all timing delays — good for leaving on a second monitor to really commit to the bit.

```bash
python vibe.py --slow "extract payment service into microservice"
python vibe.py --slow --offline "add redis caching layer"
```

### Random topic (no argument)

Picks a random topic each session and rotates through them.

```bash
python vibe.py
python vibe.py --slow
```

### Exit

`Ctrl+C` — exits cleanly and prints a session count.

---

## API key setup

Required unless using `--offline`:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

If not set, the script will tell you exactly what to do and exit.

---

## Cost

One Haiku API call per session loop. Approximately **$0.0004 per session** at current Anthropic pricing. A full day of looping is still less than a cent.
