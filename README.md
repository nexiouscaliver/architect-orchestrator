<div align="center">

# architect-orchestrator

A Claude Code plugin that turns one session into a **planning orchestrator**.

[![CI](https://github.com/nexiouscaliver/architect-orchestrator/actions/workflows/validate.yml/badge.svg)](https://github.com/nexiouscaliver/architect-orchestrator/actions/workflows/validate.yml)
[![release](https://img.shields.io/github/v/release/nexiouscaliver/architect-orchestrator?color=blue)](https://github.com/nexiouscaliver/architect-orchestrator/releases)
[![license](https://img.shields.io/github/license/nexiouscaliver/architect-orchestrator?color=blue)](./LICENSE)
[![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-7c3aed)](https://code.claude.com/docs/en/plugins)

</div>

You describe an issue or feature. The **`architect`** skill scopes it, triages it by complexity, plans it, runs review gates proportional to risk, and dispatches a team of specialist subagents to do the work — while maintaining persistent project state across sessions.

It **plans and coordinates**. It does **not** edit application code itself.

---

## Contents

- [How it works](#how-it-works)
- [The team](#the-team)
- [Install](#install)
- [Use](#use)
- [Customizing](#customizing)
- [Development (CI)](#development-ci)
- [Notes](#notes)
- [License](#license)

## How it works

```
 Intake ─▶ Triage ─▶ Plan & gate ─▶ Dispatch ─▶ Integrate ─▶ Done
 (restate)  (lane)   (critic review)  (subagents)  (verify)    ✔
                       ▲                              │
                       └───────── replan if needed ───┘
```

- **Complexity lanes.** Each task is triaged *trivial / standard / complex*; the lane decides how much process it gets.

  | Lane | Typical scope | Process it gets | Impl. model |
  | :-- | :-- | :-- | :-- |
  | **Trivial** | one file, mechanical | batch several, then one combined review | Sonnet *(Haiku if very mechanical)* |
  | **Standard** | a few files, clear scope | short plan → one review → implement → review | Sonnet |
  | **Complex / risky** | cross-cutting, security, ambiguous | spec → review → plan → review → implement → review | Opus *(reviews stay on Sonnet)* |

- **Model routing.** Each agent sets its model in frontmatter, and the architect also passes it explicitly on each dispatch for reliability. **Opus** for complex implementation, **Sonnet** for standard work and all reviews, **Haiku** for leaf tasks.

- **One human gate.** You approve the implementation plan before execution begins. Critic reviews are automatic inputs the architect must address — they don't replace your approval.

- **Persistent state.** The architect maintains `.claude/orchestrator/queue.md` (task tracking) and `memory.md` (durable decisions) in each project, so work survives across sessions.

## The team

The skill dispatches these specialist subagents:

| Agent | Role | Default model |
| :-- | :-- | :-- |
| `spec-writer` | Fuzzy request → testable spec | sonnet |
| `planner` | Approved spec → file-level plan | sonnet |
| `implementer` | Code + tests for one task | Opus / Sonnet *(by lane)* |
| `test-runner` | Run tests, return only failures | haiku |
| `code-reviewer` | Review an implemented / batched diff | sonnet |
| `debugger` | Reproduce, root-cause, minimal fix | sonnet |
| `documenter` | Docs and ADRs | sonnet |
| `critic` | Adversarial review of specs / plans / decisions | sonnet |

## Install

Launch on Opus so the architect can route hard tasks up to Opus (a subagent can't exceed the main session's tier):

```
claude --model opus
```

**Option A — marketplace install (recommended).** Add the marketplace from GitHub, then install:

```
/plugin marketplace add nexiouscaliver/architect-orchestrator
/plugin install architect-orchestrator@architect-orchestrator
```

*(A local path works too: `/plugin marketplace add /path/to/architect-orchestrator`.)*

**Option B — copy into user scope (no marketplace).** From a clone of this repo:

```
cp -r architect-orchestrator/skills/architect ~/.claude/skills/
cp    architect-orchestrator/agents/*.md      ~/.claude/agents/
```

> After editing agents/hooks in a plugin, run `/reload-plugins` or restart. `SKILL.md` edits apply immediately. Project-level `.claude/agents/` definitions override same-named plugin agents.

## Use

In your session, type `/architect` and describe the issue or feature. The skill loads on explicit invocation only (it does not auto-trigger from a description), then scopes, triages, plans, and asks for your approval before it starts dispatching.

## Customizing

- **Lanes & thresholds** live in the skill's *Complexity Lanes* section — adjust what counts as trivial vs. complex.
- **Model routing** is in the skill's *Model Routing* section.
- **Tool access** per agent is the `tools:` frontmatter field; tighten it to constrain an agent.
- **Add a specialist** — drop another file in `agents/` and add a line to the skill's *Your Team* roster so the architect knows it exists.

## Development (CI)

A CI workflow ([`.github/workflows/validate.yml`](.github/workflows/validate.yml)) runs [`scripts/validate_plugin.py`](scripts/validate_plugin.py) on every push, pull request, and tag. It checks:

- JSON validity of both manifests
- `plugin.json` schema — required fields, `repository` must be a string, `keywords` is an array
- `marketplace.json` schema — required fields, name not reserved, each plugin has a `./` source pointing at a real plugin
- version sync between `plugin.json` and the marketplace entry
- directory layout — `skills/` and `agents/` at the plugin root, not inside `.claude-plugin/`
- YAML frontmatter on the skill and every agent

Run it locally — no dependencies required:

```
python scripts/validate_plugin.py
```

## Notes

- The architect dispatches each team member explicitly by name via the Agent tool rather than relying on auto-delegation by description, so invocation is deterministic.
- Subagent-heavy runs cost several times the tokens of a single thread. The lane system exists partly to keep that in check — heavy process only where risk justifies it.

## License

[MIT](./LICENSE) © Shahil Kadia
