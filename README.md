# architect-orchestrator

A Claude Code plugin that turns one session into a planning orchestrator. You describe an issue or feature; the **architect** skill scopes it, triages it by complexity, plans it, runs review gates proportional to risk, and dispatches a team of specialist subagents to do the work — while maintaining persistent project state. It plans and coordinates; it does not edit application code itself.

## Components

**Skill** — `architect`: the orchestrator workflow. Loads into your normal session on demand via `/architect` (it does not auto-invoke on descriptions). Your project `CLAUDE.md` is never modified.

**Subagents** (the team it dispatches):

| Agent | Role | Default model |
|---|---|---|
| spec-writer | Fuzzy request → testable spec | sonnet |
| planner | Approved spec → file-level plan | sonnet |
| implementer | Code + tests for one task | per lane (architect routes) |
| test-runner | Run tests, return only failures | haiku |
| code-reviewer | Review an implemented/batched diff | sonnet |
| debugger | Reproduce, root-cause, minimal fix | sonnet |
| documenter | Docs and ADRs | sonnet |
| critic | Adversarial review of specs/plans/decisions | sonnet |

## How it works

- **Complexity lanes.** Each task is triaged *trivial / standard / complex*, and the lane decides how much process it gets. Trivial tasks skip the gates and are batched into a single review; standard tasks get a plan + one review; complex tasks get the full spec → review → plan → review → implement → review pipeline.
- **Model routing.** Each agent sets its model in frontmatter, and the architect also passes it explicitly on each dispatch for reliability. Opus for complex implementation, Sonnet for standard work and all reviews, Haiku for leaf tasks.
- **One human gate.** You approve the implementation plan before execution. Critic reviews are automatic inputs the architect must address.
- **Persistent state.** The architect maintains `.claude/orchestrator/queue.md` (task tracking) and `memory.md` (durable decisions) in each project, so work survives across sessions.

## Install

Launch on Opus so the architect can route hard tasks up to Opus (a subagent can't exceed the main session's tier):

```
claude --model opus
```

**Option A — quickest, no marketplace.** Copy the pieces into your user scope (available in every project):

```
cp -r architect-orchestrator/skills/architect ~/.claude/skills/
cp architect-orchestrator/agents/*.md ~/.claude/agents/
```

**Option B — as a versioned, shareable plugin.** Add the marketplace from GitHub, then install:

```
/plugin marketplace add nexiouscaliver/architect-orchestrator
/plugin install architect-orchestrator@architect-orchestrator
```

(Local path works too: `/plugin marketplace add /path/to/architect-orchestrator`.)

(After editing agents/hooks in a plugin, run `/reload-plugins` or restart; SKILL.md edits apply immediately. Project-level `.claude/agents/` definitions override same-named plugin agents.)

## Use

In your session, type `/architect` and describe the issue or feature. The architect will scope, triage, plan, and ask for your approval before it starts dispatching.

## Customizing

- **Lanes & thresholds** live in the skill's *Complexity Lanes* section — adjust what counts as trivial vs complex.
- **Model routing** is in the skill's *Model Routing* section.
- **Tool access** per agent is the `tools:` frontmatter field; tighten to constrain an agent.
- **Add a specialist** — drop another file in `agents/` and add a line to the skill's *Your Team* roster so the architect knows it exists.

## Notes

- Auto-delegation by description is currently unreliable in Claude Code; this works because the architect invokes its team by name.
- Subagent-heavy runs cost several times the tokens of a single thread. The lane system exists partly to keep that in check — heavy process only where risk justifies it.
