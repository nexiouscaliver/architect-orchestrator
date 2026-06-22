#!/usr/bin/env python3
"""Validate the architect-orchestrator Claude Code plugin + marketplace.

Runs locally and in CI (`python scripts/validate_plugin.py`). Exits non-zero
on any failure so CI fails fast. Dependency-free: uses PyYAML for frontmatter
if it is installed, otherwise a built-in scalar frontmatter parser (sufficient
for the single-line scalar frontmatter this repo uses).

What it checks
--------------
- JSON:        both manifests parse.
- plugin.json: required fields (name, version, description, author.name,
               license); `repository` MUST be a string (the v1.0.0 bug);
               `keywords` is a list if present.
- marketplace: required fields (name, owner.name, plugins[]); name not in the
               reserved list; each plugin has `name` + `source` starting with
               `./`; the source dir actually contains a plugin manifest.
- versions:    plugin.json version matches the marketplace plugin entry.
- layout:      skills/ and agents/ live at the plugin root (siblings of
               .claude-plugin/), NOT inside .claude-plugin/ (common mistake).
- frontmatter: SKILL.md has name + description; every agent has name
               (matching its filename), description, tools, model.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # repo = marketplace root
CP = ROOT / ".claude-plugin"

# Marketplace names reserved for official Anthropic use (cannot be used by
# third parties). Mirrors the official plugin-marketplaces docs.
RESERVED_MARKETPLACE_NAMES = {
    "claude-code-marketplace", "claude-code-plugins", "claude-plugins-official",
    "claude-plugins-community", "claude-community", "anthropic-marketplace",
    "anthropic-plugins", "agent-skills", "anthropic-agent-skills",
    "knowledge-work-plugins", "life-sciences", "claude-for-legal",
    "claude-for-financial-services", "financial-services-plugins",
}

KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+].+)?$")

# Known Claude Code agent model tiers. Unknown values warn but do not fail,
# so the check does not break when new tiers ship.
KNOWN_MODELS = {"opus", "sonnet", "haiku", "inherit", "default"}

errors: list[str] = []
warnings: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)
    print(f"  [FAIL] {msg}")


def warn(msg: str) -> None:
    warnings.append(msg)
    print(f"  [WARN] {msg}")


def ok(msg: str) -> None:
    print(f"  [OK]  {msg}")


def load_json(path: Path) -> dict | None:
    if not path.exists():
        fail(f"missing manifest: {path.relative_to(ROOT)}")
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        fail(f"invalid JSON in {path.relative_to(ROOT)}: {e}")
        return None


def frontmatter(path: Path) -> dict[str, str] | None:
    """Return frontmatter as a {key: value} dict (values coerced to str)."""
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        fail(f"no YAML frontmatter block in {path.relative_to(ROOT)}")
        return None
    raw = m.group(1)
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(raw) or {}
    except ImportError:
        data = _scalar_frontmatter(raw)
    # coerce everything to string for uniform checks
    return {str(k): ("" if v is None else str(v)) for k, v in data.items()}


def _scalar_frontmatter(raw: str) -> dict[str, str]:
    """Minimal parser for single-line scalar frontmatter (no deps)."""
    out: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.rstrip()
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] in "\"'" and v[-1] == v[0]:
            v = v[1:-1]
        out[k] = v
    return out


def require_nonempty(obj: dict, key: str, where: str) -> str:
    val = str(obj.get(key, "")).strip()
    if not val:
        fail(f"{where}: missing or empty '{key}'")
    return val


def main() -> int:
    print("== manifests ==")
    plugin = load_json(CP / "plugin.json")
    market = load_json(CP / "marketplace.json")
    if plugin:
        ok("plugin.json parses")
    if market:
        ok("marketplace.json parses")
    if not (plugin and market):
        return _finish()

    # --- plugin.json schema ---
    print("\n== plugin.json schema ==")
    name = require_nonempty(plugin, "name", "plugin.json")
    if name and not KEBAB.match(name):
        fail(f"plugin.json: 'name' must be kebab-case, got {name!r}")
    if "version" not in plugin or not SEMVER.match(str(plugin["version"])):
        fail(f"plugin.json: 'version' must be semver, got {plugin.get('version')!r}")
    require_nonempty(plugin, "description", "plugin.json")
    author = plugin.get("author")
    if not isinstance(author, dict) or not str(author.get("name", "")).strip():
        fail("plugin.json: 'author.name' missing or empty")
    require_nonempty(plugin, "license", "plugin.json")
    # THE v1.0.0 check: repository must be a string, not an object.
    if "repository" in plugin and not isinstance(plugin["repository"], str):
        fail(f"plugin.json: 'repository' must be a string, got {type(plugin['repository']).__name__}")
    if "keywords" in plugin and not isinstance(plugin["keywords"], list):
        fail("plugin.json: 'keywords' must be an array")
    ok("plugin.json schema")

    # --- marketplace.json schema ---
    print("\n== marketplace.json schema ==")
    mname = require_nonempty(market, "name", "marketplace.json")
    if mname and not KEBAB.match(mname):
        fail(f"marketplace.json: 'name' must be kebab-case, got {mname!r}")
    if mname in RESERVED_MARKETPLACE_NAMES:
        fail(f"marketplace.json: name {mname!r} is reserved for official use")
    owner = market.get("owner")
    if not isinstance(owner, dict) or not str(owner.get("name", "")).strip():
        fail("marketplace.json: 'owner.name' missing or empty")
    plugins = market.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        fail("marketplace.json: 'plugins' must be a non-empty array")
    else:
        for entry in plugins:
            ename = require_nonempty(entry, "name", "marketplace plugin entry")
            src = str(entry.get("source", "")).strip()
            if not src:
                fail(f"marketplace plugin {ename!r}: missing 'source'")
            elif not src.startswith("./"):
                fail(f"marketplace plugin {ename!r}: 'source' must start with './' (got {src!r})")
            else:
                # Resolve and confirm the source stays within the marketplace
                # root. This blocks ../ traversal and symlink escape. Symlinks
                # that resolve *within* the root are allowed (the plugin spec
                # supports them for sharing files across plugins).
                plugin_dir = (ROOT / src).resolve()
                try:
                    plugin_dir.relative_to(ROOT)
                except ValueError:
                    fail(f"marketplace plugin {ename!r}: source {src!r} escapes the marketplace root")
                    continue
                if not (plugin_dir / ".claude-plugin" / "plugin.json").exists():
                    fail(f"marketplace plugin {ename!r}: source {src!r} has no .claude-plugin/plugin.json")
    ok("marketplace.json schema")

    # --- version sync ---
    print("\n== version sync ==")
    if isinstance(plugins, list) and plugins:
        mp_ver = str(plugins[0].get("version", "")).strip()
        pj_ver = str(plugin.get("version", "")).strip()
        if mp_ver and pj_ver and mp_ver != pj_ver:
            fail(f"version mismatch: plugin.json={pj_ver!r} vs marketplace entry={mp_ver!r}")
        else:
            ok(f"versions in sync ({pj_ver})")

    # --- layout: components at plugin root, NOT inside .claude-plugin/ ---
    print("\n== directory layout ==")
    for bad in (CP / "skills", CP / "agents", CP / "commands", CP / "hooks"):
        if bad.exists():
            fail(f"{bad.relative_to(ROOT)}: components must be at the plugin root, not inside .claude-plugin/")
    skills_dir = ROOT / "skills"
    agents_dir = ROOT / "agents"
    skill_files = sorted(skills_dir.glob("*/SKILL.md")) if skills_dir.exists() else []
    agent_files = sorted(agents_dir.glob("*.md")) if agents_dir.exists() else []
    if not skill_files:
        fail("no skills/*/SKILL.md found (skills/ missing or empty)")
    if not agent_files:
        fail("no agents/*.md found (agents/ missing or empty)")
    if skill_files and agent_files:
        ok(f"layout: {len(skill_files)} skill(s), {len(agent_files)} agent(s) at plugin root")

    # --- skill frontmatter ---
    print("\n== skill frontmatter ==")
    for sf in skill_files:
        fm = frontmatter(sf)
        if fm is None:
            continue
        if not fm.get("name", "").strip():
            fail(f"{sf.relative_to(ROOT)}: frontmatter missing 'name'")
        if not fm.get("description", "").strip():
            fail(f"{sf.relative_to(ROOT)}: frontmatter missing 'description'")
        ok(f"{sf.relative_to(ROOT)}: name={fm.get('name')!r}")

    # --- agent frontmatter ---
    print("\n== agent frontmatter ==")
    for af in agent_files:
        fm = frontmatter(af)
        if fm is None:
            continue
        aname = fm.get("name", "").strip()
        if not aname:
            fail(f"{af.relative_to(ROOT)}: frontmatter missing 'name'")
        elif aname != af.stem:
            fail(f"{af.relative_to(ROOT)}: name {aname!r} does not match filename stem {af.stem!r}")
        if not fm.get("description", "").strip():
            fail(f"{af.relative_to(ROOT)}: frontmatter missing 'description'")
        if not fm.get("tools", "").strip():
            fail(f"{af.relative_to(ROOT)}: frontmatter missing 'tools'")
        model = fm.get("model", "").strip()
        if not model:
            fail(f"{af.relative_to(ROOT)}: frontmatter missing 'model'")
        elif model not in KNOWN_MODELS:
            warn(f"{af.relative_to(ROOT)}: model {model!r} not in known set {sorted(KNOWN_MODELS)}")
        ok(f"{af.relative_to(ROOT)}: name={aname!r} model={model!r}")

    return _finish()


def _finish() -> int:
    print()
    if warnings:
        print(f"{len(warnings)} warning(s).")
    if errors:
        print(f"❌ {len(errors)} error(s) — validation failed.")
        return 1
    print("✅ All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
