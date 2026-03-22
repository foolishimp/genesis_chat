# Release Process Conventions

**Governance**: Maintained by the methodology author. Read-only for agents.

**NOTE TO LLM**: If this file is referenced in a prompt, it is an active instruction to execute a release following this process exactly. Do not skip steps. Do not reorder steps.

---

## Version Numbering

```
MAJOR.MINOR.PATCH
```

| Increment | When |
|-----------|------|
| `PATCH` | Bug fix — no new REQ keys, no interface changes, no new commands |
| `MINOR` | New feature — new REQ keys, new commands, new public behaviour. Backward compatible. |
| `MAJOR` | Breaking change — removed commands, changed interfaces, incompatible workspace format |

**Rule**: Adding REQ keys is always at least a MINOR bump. The spec_hash changes, which invalidates all prior `assessed{kind: fp}` events in dependent projects — that is a breaking change to the convergence state.

**Rule**: Any change to installer assets (bootloader, operating standards, commands) requires at least a MINOR bump. These assets are deployed by the installer — a version bump signals to dependent projects that re-running the installer will update their workspace.

---

## Files to Update on Every Release

Update ALL of these atomically — a partial version bump is a defect:

| File | Field |
|------|-------|
| `builds/python/src/genesis_sdlc/install.py` | `VERSION = "x.y.z"` |
| `builds/python/src/genesis_sdlc/install.py` | `BOOTLOADER_VERSION = "x.y.z"` — bump if bootloader changed |
| `builds/python/src/genesis_sdlc/__init__.py` | `__version__ = "x.y.z"` |
| `builds/python/pyproject.toml` | `version = "x.y.z"` |
| `builds/python/tests/test_sdlc_graph.py` | `assert genesis_sdlc.__version__ == "x.y.z"` |
| `builds/python/tests/test_installer.py` | `assert data["version"] == "x.y.z"` |
| `builds/python/CHANGELOG.md` | New entry (see format below) |

---

## CHANGELOG Format

File location: `builds/python/CHANGELOG.md` — newest entry at the top.

```markdown
## v{VERSION} — {YYYY-MM-DD}

**Bootloader**: v{X.Y.Z}
**Spec hash**: {sha256[:16] of Package.requirements}
**Test results**: {N passed, N skipped, 0 failed}

### Added
- {bullet per new feature or REQ group}

### Changed
- {bullet per modified behaviour or installer asset}

### Fixed
- {bullet per bug fix}

**REQ keys added**: {comma-separated list, or "none"}
```

`spec_hash` allows downstream operators and automation to determine whether upgrading
genesis_sdlc will invalidate their existing `assessed{kind: fp}` events (a changed spec_hash
means all F_P assessments are stale and will be re-dispatched on next `gen-start`).

`Bootloader` version lets operators know which bootloader their installed CLAUDE.md carries
after running the installer.

---

## Release Steps

### 1. Verify all tests pass

```bash
PYTHONPATH=builds/python/src:.genesis python -m pytest builds/python/tests/ -m 'not e2e'
```

All must pass. Do not proceed with failures.

### 1b. Check bootloader for changes

```bash
git diff HEAD .genesis/gtl_spec/GENESIS_BOOTLOADER.md
```

If changed:
- Bump the `**Version**:` line inside `GENESIS_BOOTLOADER.md`
- Update `BOOTLOADER_VERSION` in `builds/python/src/genesis_sdlc/install.py`
- The genesis_sdlc version must be at least a MINOR bump

If unchanged: confirm `BOOTLOADER_VERSION` in `install.py` still matches the `**Version**:` line in the file.

### 2. Bump version

Update all files in the table above to the new version string.

### 2b. Write CHANGELOG entry

Append a new entry to `builds/python/CHANGELOG.md` using the format above.

Compute spec_hash (must match the engine's `req_hash()` — JSON-sorted):
```bash
PYTHONPATH=.genesis python -c "
import json, hashlib, importlib.util
spec = importlib.util.spec_from_file_location('s', 'builds/python/src/genesis_sdlc/sdlc_graph.py')
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
print(hashlib.sha256(json.dumps(sorted(mod.package.requirements)).encode()).hexdigest()[:16])
"
```

### 3. Run tests again

Verify the version bump did not break anything:

```bash
PYTHONPATH=builds/python/src:.genesis python -m pytest builds/python/tests/ -m 'not e2e'
```

### 4. Verify gaps converged

```bash
PYTHONPATH=.genesis python -m genesis gaps --workspace .
```

`converged: true` required. If not, the release has introduced a spec change that invalidates prior assessments — drive to convergence before releasing.

### 5. Commit

```bash
git add -A
git commit -m "feat(v{VERSION}): {short description of what changed}"
```

Commit message format: `feat` for new features, `fix` for bug fixes, `chore` for tooling/process changes.

### 6. Tag and push

```bash
git tag v{VERSION}
git push origin main --tags
```

### 7. Cascade install to all dependent projects

Run the installer against every project in the Known Dependent Projects list.
`genesis_sdlc` itself is always first — it is a dependent like any other.

```bash
PYTHONPATH=builds/python/src:.genesis python -m genesis_sdlc.install \
  --target /path/to/project \
  --project-slug {slug}
```

Commit the updated artifacts in each project that is a git repo:

```bash
cd /path/to/project
git add .claude/ .genesis/ CLAUDE.md .ai-workspace/operating-standards/
git commit -m "chore: cascade genesis_sdlc v{VERSION}"
git push origin main
```

### 8. Emit release event

```bash
PYTHONPATH=.genesis python -m genesis emit-event \
  --type genesis_sdlc_released \
  --data '{"version": "{VERSION}", "bootloader_version": "{BOOTLOADER_VERSION}", "spec_hash": "{SPEC_HASH}", "summary": "{short description}"}'
```

---

## Known Dependent Projects

Run the cascade installer against all of these on every release, starting with `genesis_sdlc` itself.

| Project | Slug | Notes |
|---------|------|-------|
| `genesis_sdlc` | `genesis_sdlc` | Always first — updates its own commands, bootloader, standards |
| `genesis-manager` | `genesis_manager` | |
| `abiogenesis` | `abiogenesis` | Dogfood: genesis_sdlc builds the engine that runs genesis_sdlc |
| `gen_enterprise_arch` | `gen_enterprise_arch` | No git repo — install only |
| `genesis_chat` | `genesis_chat` | No git repo — install only |

---

## What Does Not Need a Release

- Editing comment posts in `.ai-workspace/comments/` — these are workspace artifacts, not versioned artifacts
- Editing ADRs in `builds/python/design/adrs/` — ADRs are immutable; supersede with a new ADR

**Note**: Editing `specification/standards/` files (operating standards) DOES require a release — they are installer assets deployed to dependent projects. Update the source, bump the version (MINOR), cascade, commit.
