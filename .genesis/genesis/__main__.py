# Implements: REQ-F-CMD-001
# Implements: REQ-F-CMD-002
# Implements: REQ-F-CMD-003
# Implements: REQ-F-TAG-001
# Implements: REQ-F-TAG-002
# Implements: REQ-F-COV-001
# Implements: REQ-F-EVAL-001
# Implements: REQ-F-EVAL-003
# Implements: REQ-F-EVAL-004
# Implements: REQ-F-DOCS-001
# Implements: REQ-F-PROV-002
# Implements: REQ-F-BOOTDOC-001
# Implements: REQ-F-BOOTDOC-002
# Implements: REQ-F-BOOTDOC-003
"""
__main__ — CLI entry point for the genesis engine.

Usage:
  python -m genesis start  [--auto] [--human-proxy] [--feature F] [--edge E] [--workspace W]
  python -m genesis iterate [--feature F] [--edge E] [--workspace W]
  python -m genesis gaps    [--feature F] [--workspace W]
  python -m genesis emit-event --type TYPE [--data JSON] [--workspace W]
  python -m genesis check-tags --type implements|validates --path PATH

  gen start ...   (via project.scripts entry point)

Exit codes for start/iterate:
  0 — converged or nothing_to_do
  1 — error
  2 — fp_dispatched (F_P actor required; fp_manifest_path in output)
  3 — fh_gate_pending (F_H evaluation required; gate criteria in output)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="genesis",
        description="Genesis engine — GTL-first AI SDLC V1",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── gen start ────────────────────────────────────────────────────────────
    p_start = sub.add_parser("start", help="Derive state → bind → iterate")
    p_start.add_argument("--auto", action="store_true",
                         help="Loop until converged or blocked by F_H gate")
    p_start.add_argument("--human-proxy", action="store_true",
                         help="Allow F_H gates to be evaluated by proxy (requires --auto)")
    p_start.add_argument("--feature", metavar="F",
                         help="Scope to a specific feature vector ID")
    p_start.add_argument("--edge", metavar="E",
                         help="Override edge selection")
    p_start.add_argument("--workspace", metavar="W", default=".",
                         help="Workspace root (default: cwd)")

    # ── gen iterate ───────────────────────────────────────────────────────────
    p_iter = sub.add_parser("iterate", help="Bind one Job → iterate exactly once")
    p_iter.add_argument("--feature", metavar="F", help="Feature vector ID")
    p_iter.add_argument("--edge", metavar="E", help="Edge name")
    p_iter.add_argument("--workspace", metavar="W", default=".",
                        help="Workspace root (default: cwd)")

    # ── gen gaps ──────────────────────────────────────────────────────────────
    p_gaps = sub.add_parser("gaps", help="bind_fd over scope → delta summary")
    p_gaps.add_argument("--feature", metavar="F",
                        help="Scope to a specific feature vector ID")
    p_gaps.add_argument("--workspace", metavar="W", default=".",
                        help="Workspace root (default: cwd)")

    # --package / --worker on all three engine commands
    for p in (p_start, p_iter, p_gaps):
        p.add_argument("--package", metavar="MODULE:VAR",
                       help="Package to load (overrides .genesis/genesis.yml)")
        p.add_argument("--worker", metavar="MODULE:VAR",
                       help="Worker to load (overrides .genesis/genesis.yml)")

    # ── emit-event ────────────────────────────────────────────────────────────
    p_emit = sub.add_parser("emit-event",
                            help="Append one event to .ai-workspace/events/events.jsonl")
    p_emit.add_argument("--type", required=True, metavar="TYPE",
                        help="Event type (e.g. approved, assessed, revoked)")
    p_emit.add_argument("--data", default="{}", metavar="JSON",
                        help="Event data as a JSON object (default: {})")
    p_emit.add_argument("--workspace", metavar="W", default=".",
                        help="Workspace root (default: cwd)")

    # ── check-tags ────────────────────────────────────────────────────────────
    p_tags = sub.add_parser("check-tags",
                            help="Verify Implements:/Validates: tags in source files")
    p_tags.add_argument("--type", choices=["implements", "validates"], required=True,
                        help="Tag type to check")
    p_tags.add_argument("--path", required=True,
                        help="Directory to scan")

    # ── check-req-coverage ────────────────────────────────────────────────────
    p_cov = sub.add_parser("check-req-coverage",
                           help="Verify every REQ-* key in spec appears in a feature vector")
    src = p_cov.add_mutually_exclusive_group(required=True)
    src.add_argument("--spec",
                     help="Path to spec file to grep for REQ-* keys (legacy)")
    src.add_argument("--package", metavar="MODULE:VAR",
                     help="Import path to a Package object, e.g. gtl_spec.packages.genesis_core:genesis_v1")
    p_cov.add_argument("--features", required=True,
                       help="Directory containing feature vector YAML files")

    # ── check-impl-coverage ───────────────────────────────────────────────────
    p_impl = sub.add_parser("check-impl-coverage",
                            help="Verify every REQ-* key appears in a # Implements: tag")
    p_impl.add_argument("--package", required=True, metavar="MODULE:VAR",
                        help="Package to load requirements from")
    p_impl.add_argument("--path", required=True,
                        help="Directory to scan for # Implements: tags")

    # ── check-validates-coverage ──────────────────────────────────────────────
    p_val = sub.add_parser("check-validates-coverage",
                           help="Verify every REQ-* key appears in a # Validates: tag")
    p_val.add_argument("--package", required=True, metavar="MODULE:VAR",
                       help="Package to load requirements from")
    p_val.add_argument("--path", required=True,
                       help="Directory to scan for # Validates: tags")

    # ── check-bootloader-consistency ─────────────────────────────────────────
    p_boot = sub.add_parser("check-bootloader-consistency",
                            help="Verify bootloader doc references all exported types from spec module")
    p_boot.add_argument("--spec-module", required=True,
                        help="Python module to extract exported type names from (e.g. gtl.core)")
    p_boot.add_argument("--bootloader", required=True,
                        help="Path to bootloader markdown file (relative to workspace)")

    return parser


def _check_tags(tag_type: str, scan_path: str) -> int:
    """
    Scan .py files for required tags.

    Implements: checks for '# Implements:'
    Validates:  checks for '# Validates:'

    Exits 0 if all files are tagged, 1 if any are untagged.
    Prints untagged file paths to stdout.
    """
    tag = "# Implements:" if tag_type == "implements" else "# Validates:"
    path = Path(scan_path)

    if not path.exists():
        print(f"ERROR: path does not exist: {path}", file=sys.stderr)
        return 1

    untagged = []
    for f in sorted(path.rglob("*.py")):
        if f.name == "__init__.py":
            continue
        if tag not in f.read_text(encoding="utf-8"):
            untagged.append(str(f))

    result = {
        "tag": tag,
        "path": str(path),
        "scanned": len([f for f in path.rglob("*.py") if f.name != "__init__.py"]),
        "untagged_count": len(untagged),
        "untagged": untagged,
        "passes": len(untagged) == 0,
    }
    print(json.dumps(result, indent=2))
    return 0 if result["passes"] else 1


def _check_req_coverage(spec_path: str, features_dir: str,
                        package_ref: str | None = None) -> int:
    """
    Verify every REQ-* key in the spec appears in at least one feature vector.

    Two source modes:
      package_ref  — import MODULE:VAR, read Package.requirements (authoritative)
      spec_path    — grep the file for REQ-* tokens (legacy / fallback)

    Exits 0 if all keys covered, 1 if any gaps exist.
    Prints a JSON result to stdout.
    """
    import re

    features = Path(features_dir)
    if not features.exists():
        print(json.dumps({"error": f"features dir not found: {features_dir}"}), file=sys.stderr)
        return 1

    # ── Resolve spec_keys ────────────────────────────────────────────────────
    if package_ref:
        # Package-authoritative path: MODULE:VAR
        if ":" not in package_ref:
            print(json.dumps({"error": f"--package must be MODULE:VAR, got {package_ref!r}"}),
                  file=sys.stderr)
            return 1
        module_name, var_name = package_ref.rsplit(":", 1)
        try:
            import importlib
            mod = importlib.import_module(module_name)
        except ImportError as exc:
            print(json.dumps({"error": f"cannot import {module_name}: {exc}"}), file=sys.stderr)
            return 1
        pkg = getattr(mod, var_name, None)
        if pkg is None:
            print(json.dumps({"error": f"{var_name!r} not found in {module_name}"}),
                  file=sys.stderr)
            return 1
        spec_keys = set(getattr(pkg, "requirements", []))
        source = f"package:{package_ref}"
    else:
        # Grep-based legacy path
        spec = Path(spec_path)
        if not spec.exists():
            print(json.dumps({"error": f"spec not found: {spec_path}"}), file=sys.stderr)
            return 1
        spec_text = spec.read_text(encoding="utf-8")
        spec_keys = set(re.findall(r"REQ-[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*", spec_text))
        source = str(spec_path)

    # ── Scan feature vectors for covered keys ────────────────────────────────
    covered_keys: set[str] = set()
    for yml in features.rglob("*.yml"):
        text = yml.read_text(encoding="utf-8")
        covered_keys.update(re.findall(r"REQ-[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*", text))

    uncovered = sorted(spec_keys - covered_keys)
    result = {
        "spec": source,
        "features_dir": features_dir,
        "spec_keys": sorted(spec_keys),
        "covered_count": len(spec_keys) - len(uncovered),
        "total_count": len(spec_keys),
        "uncovered": uncovered,
        "passes": len(uncovered) == 0,
    }
    print(json.dumps(result, indent=2))
    return 0 if result["passes"] else 1


def _check_tag_coverage(tag_type: str, package_ref: str, scan_path: str) -> int:
    """
    Verify every REQ-* key in Package.requirements appears in at least one file
    with the appropriate tag (# Implements: or # Validates:).

    This is the per-key complement to check-tags (which checks file-level presence).
    A new REQ key with no Implements/Validates tag causes this check to fail,
    making spec evolution deterministically detectable by F_D.
    """
    import importlib
    import re

    if ":" not in package_ref:
        print(json.dumps({"error": f"--package must be MODULE:VAR, got {package_ref!r}"}),
              file=sys.stderr)
        return 1

    module_name, var_name = package_ref.rsplit(":", 1)
    try:
        mod = importlib.import_module(module_name)
    except ImportError as exc:
        print(json.dumps({"error": f"cannot import {module_name}: {exc}"}), file=sys.stderr)
        return 1

    pkg = getattr(mod, var_name, None)
    if pkg is None:
        print(json.dumps({"error": f"{var_name!r} not found in {module_name}"}),
              file=sys.stderr)
        return 1

    req_keys = list(getattr(pkg, "requirements", []))
    path = Path(scan_path)
    if not path.exists():
        print(json.dumps({"error": f"path not found: {scan_path}"}), file=sys.stderr)
        return 1

    tag_prefix = "# Implements:" if tag_type == "implements" else "# Validates:"

    # Collect all REQ-* keys found in matching tag lines across all .py files
    tagged_keys: set[str] = set()
    for f in path.rglob("*.py"):
        if f.name == "__init__.py":
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            if tag_prefix in line:
                tagged_keys.update(re.findall(r"REQ-[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*", line))

    missing = sorted(set(req_keys) - tagged_keys)
    result = {
        "tag_type": tag_type,
        "path": str(path),
        "spec_keys": sorted(req_keys),
        "tagged_count": len(req_keys) - len(missing),
        "total_count": len(req_keys),
        "missing": missing,
        "passes": len(missing) == 0,
    }
    print(json.dumps(result, indent=2))
    return 0 if result["passes"] else 1


def _check_bootloader_consistency(spec_module: str, bootloader_path: str) -> int:
    """
    # Implements: REQ-F-BOOTDOC-002
    Verify that all public GTL type names defined in a spec module appear in the
    bootloader doc.

    Extracts classes defined in the module (not imported from stdlib) and checks
    each appears in the bootloader markdown. Exits 0 if all present, 1 with gap list.
    """
    import importlib
    import inspect

    try:
        mod = importlib.import_module(spec_module)
    except ImportError as exc:
        print(json.dumps({"error": f"cannot import {spec_module}: {exc}"}),
              file=sys.stderr)
        return 1

    # Extract classes actually defined in the module (not imported from stdlib).
    # Filter to public names only (no underscore prefix).
    all_defined = sorted(
        name for name, obj in inspect.getmembers(mod)
        if inspect.isclass(obj)
        and obj.__module__ == spec_module
        and not name.startswith("_")
    )

    # The bootloader is contractually required to reference the core GTL primitives
    # (the types used in Package definitions). Internal implementation types
    # (IterateProtocol, Operative, Overlay, PackageSnapshot, WorkingSurface) are
    # not required in the bootloader — they are implementation details.
    _CORE_TYPES = {
        "Asset", "Context", "Edge", "Evaluator",
        "F_D", "F_H", "F_P",
        "Job", "Operator", "Package", "Rule", "Worker",
    }
    exported = sorted(name for name in all_defined if name in _CORE_TYPES)

    # Read bootloader
    boot_path = Path(bootloader_path)
    if not boot_path.exists():
        print(json.dumps({"error": f"bootloader not found: {bootloader_path}"}),
              file=sys.stderr)
        return 1

    boot_text = boot_path.read_text(encoding="utf-8")

    # Check each exported name appears in the bootloader
    missing = [name for name in exported if name not in boot_text]

    result = {
        "spec_module": spec_module,
        "bootloader": bootloader_path,
        "exported_types": exported,
        "exported_count": len(exported),
        "missing": missing,
        "passes": len(missing) == 0,
    }
    print(json.dumps(result, indent=2))
    return 0 if result["passes"] else 1


def _emit_event_cmd(event_type: str, data_json: str, workspace: Path) -> int:
    """
    Append one event to .ai-workspace/events/events.jsonl.

    This is an F_D-controlled write path called by the skill layer (gen-start.md),
    never by F_P actors directly. F_P actors write to result_path; the skill reads
    the result and calls emit-event. See GENESIS_BOOTLOADER §V (event-time invariant).

    Governance: required fields validated per event type (prime operators).
      approved  — requires: kind (fh_review | fh_intent), edge, actor (human | human-proxy)
        human-proxy actor additionally requires: proxy_log
      assessed  — requires: kind, edge, evaluator, result (pass | fail)
        kind=fp additionally requires: spec_hash
      revoked   — requires: kind (fh_approval), edge, actor, reason
    """
    import json as _json
    from datetime import datetime, timezone

    from genesis.commands import _read_workflow_version

    try:
        data = _json.loads(data_json)
    except _json.JSONDecodeError as exc:
        print(f"ERROR: --data is not valid JSON: {exc}", file=sys.stderr)
        return 1

    # Governance validation — required fields per prime event types
    errors: list[str] = []
    if event_type == "approved":
        if "kind" not in data:
            errors.append("approved requires 'kind' field (fh_review | fh_intent)")
        if "edge" not in data:
            errors.append("approved requires 'edge' field")
        if "actor" not in data:
            errors.append("approved requires 'actor' field (human | human-proxy)")
        elif data["actor"] == "human-proxy" and "proxy_log" not in data:
            errors.append("human-proxy actor requires 'proxy_log' path field")
    elif event_type == "assessed":
        # Assessed has two schemas split by kind:
        #   kind=fp       — F_P agent assessment: requires evaluator, spec_hash
        #   kind=fh_review — F_H human rejection: requires actor, reason
        for fld in ("kind", "edge", "result"):
            if fld not in data:
                errors.append(f"assessed requires '{fld}' field")
        kind = data.get("kind")
        if kind == "fp":
            # REQ-F-EVAL-004: spec_hash required so bind_fd() can validate snapshot.
            for fld in ("evaluator", "spec_hash"):
                if fld not in data:
                    errors.append(f"assessed{{kind: fp}} requires '{fld}' field")
            if data.get("result") not in (None, "pass", "fail"):
                errors.append("assessed{kind: fp} 'result' must be 'pass' or 'fail'")
        elif kind == "fh_review":
            for fld in ("actor", "reason"):
                if fld not in data:
                    errors.append(f"assessed{{kind: fh_review}} requires '{fld}' field")
            if data.get("result") not in (None, "reject"):
                errors.append("assessed{kind: fh_review} 'result' must be 'reject'")
    elif event_type == "revoked":
        for fld in ("kind", "edge", "actor", "reason"):
            if fld not in data:
                errors.append(f"revoked requires '{fld}' field")

    if errors:
        for msg in errors:
            print(f"ERROR: {msg}", file=sys.stderr)
        return 1

    # Annotate workflow_version from active-workflow.json (REQ-F-PROV-002).
    # Reads the file directly — emit-event runs pre-stack without a Scope object.
    data["workflow_version"] = _read_workflow_version(workspace)

    events_dir = workspace / ".ai-workspace" / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    event = {
        "event_type": event_type,
        "event_time": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
    events_file = events_dir / "events.jsonl"
    with events_file.open("a", encoding="utf-8") as f:
        f.write(_json.dumps(event) + "\n")

    print(_json.dumps({"status": "ok", "event_type": event_type}))
    return 0


def _load_project_config(workspace: Path) -> dict:
    """
    Read .genesis/genesis.yml — key: value pairs and YAML lists.

    Returns a dict with 'package', 'worker', and/or 'pythonpath' keys.
    'pythonpath' is returned as a list[str].
    Returns empty dict if the file does not exist.
    """
    config_path = workspace / ".genesis" / "genesis.yml"
    if not config_path.exists():
        return {}
    config: dict = {}
    current_list_key: str | None = None
    for line in config_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            current_list_key = None
            continue
        # YAML list item under a current list key
        if current_list_key is not None and stripped.startswith("- "):
            config[current_list_key].append(stripped[2:].strip())
            continue
        current_list_key = None
        if ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()
            if val == "":
                # Key with no inline value — start a list
                config[key] = []
                current_list_key = key
            else:
                config[key] = val
    return config


def _import_symbol(ref: str, workspace: Path):
    """
    Import MODULE:VAR from workspace. Returns the symbol.

    Raises ValueError if ref has no colon.
    Raises ImportError if the module or variable cannot be found.
    """
    if ":" not in ref:
        raise ValueError(f"Expected MODULE:VAR, got {ref!r}")
    module_name, _, var_name = ref.partition(":")
    import importlib
    try:
        mod = importlib.import_module(module_name)
    except ImportError as exc:
        raise ImportError(f"Cannot import {module_name!r}: {exc}") from exc
    sym = getattr(mod, var_name, None)
    if sym is None:
        raise ImportError(f"{var_name!r} not found in {module_name!r}")
    return sym


def _resolve_package_worker(args, workspace: Path):
    """
    Resolve Package and Worker.

    Precedence: --package/--worker flags > .genesis/genesis.yml > error.
    Validates symbol types. Exits with code 1 on any failure.
    """
    pkg_ref = getattr(args, "package", None) or None
    wrk_ref = getattr(args, "worker", None) or None

    if not pkg_ref or not wrk_ref:
        config = _load_project_config(workspace)
        pkg_ref = pkg_ref or config.get("package")
        wrk_ref = wrk_ref or config.get("worker")

    if not pkg_ref or not wrk_ref:
        print(
            "ERROR: no package/worker configured.\n"
            "  Pass --package MODULE:VAR --worker MODULE:VAR, or\n"
            "  run gen-install.py to create .genesis/genesis.yml",
            file=sys.stderr,
        )
        sys.exit(1)

    from gtl.core import Package, Worker

    try:
        package = _import_symbol(pkg_ref, workspace)
    except (ImportError, ValueError) as exc:
        print(f"ERROR: --package {pkg_ref!r}: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        worker = _import_symbol(wrk_ref, workspace)
    except (ImportError, ValueError) as exc:
        print(f"ERROR: --worker {wrk_ref!r}: {exc}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(package, Package):
        print(
            f"ERROR: {pkg_ref!r} resolved to {type(package).__name__}, expected Package",
            file=sys.stderr,
        )
        sys.exit(1)

    if not isinstance(worker, Worker):
        print(
            f"ERROR: {wrk_ref!r} resolved to {type(worker).__name__}, expected Worker",
            file=sys.stderr,
        )
        sys.exit(1)

    return package, worker


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # Lightweight commands — no engine stack needed
    if args.command == "check-tags":
        sys.exit(_check_tags(args.type, args.path))
    if args.command == "check-req-coverage":
        sys.exit(_check_req_coverage(
            spec_path=args.spec or "",
            features_dir=args.features,
            package_ref=getattr(args, "package", None),
        ))
    if args.command == "check-impl-coverage":
        sys.exit(_check_tag_coverage("implements", args.package, args.path))
    if args.command == "check-validates-coverage":
        sys.exit(_check_tag_coverage("validates", args.package, args.path))
    if args.command == "check-bootloader-consistency":
        sys.exit(_check_bootloader_consistency(args.spec_module, args.bootloader))

    # emit-event: appends one event to events.jsonl — no engine stack needed
    if args.command == "emit-event":
        workspace = Path(args.workspace).resolve()
        sys.exit(_emit_event_cmd(args.type, args.data, workspace))

    # --human-proxy requires --auto
    if getattr(args, "human_proxy", False) and not getattr(args, "auto", False):
        print(json.dumps({"status": "error",
                          "reason": "--human-proxy requires --auto"}))
        sys.exit(1)

    # All other commands need the engine
    workspace = Path(getattr(args, "workspace", ".")).resolve()

    # Ensure spec is importable from workspace root
    if str(workspace) not in sys.path:
        sys.path.insert(0, str(workspace))

    # Insert pythonpath entries from genesis.yml (resolved relative to workspace)
    _config = _load_project_config(workspace)
    for _extra in reversed(_config.get("pythonpath", [])):
        _extra_path = str((workspace / _extra).resolve())
        if _extra_path not in sys.path:
            sys.path.insert(0, _extra_path)

    from .core import workspace_bootstrap
    stream = workspace_bootstrap(workspace)

    from .commands import Scope, gen_gaps, gen_iterate, gen_start

    package, worker = _resolve_package_worker(args, workspace)

    scope = Scope(
        package=package,
        workspace_root=workspace,
        feature=getattr(args, "feature", None),
        edge=getattr(args, "edge", None),
        worker=worker,
    )

    if args.command == "start":
        human_proxy = getattr(args, "human_proxy", False)
        result = gen_start(scope, stream, auto=getattr(args, "auto", False))
        # Surface proxy mode so the skill can confirm its operating context
        if human_proxy:
            result["human_proxy"] = True
    elif args.command == "iterate":
        result = gen_iterate(scope, stream)
    elif args.command == "gaps":
        result = gen_gaps(scope, stream)
    else:
        parser.print_help()
        sys.exit(1)

    print(json.dumps(result, indent=2))

    # Exit codes for skill routing:
    #   0 — converged / nothing_to_do  (loop complete)
    #   1 — error (already exited above)
    #   2 — fp_dispatched (F_P actor required; fp_manifest_path in output)
    #   3 — fh_gate_pending (F_H evaluation required; fh_gate.criteria in output)
    #   4 — fd_gap (deterministic checks still failing after F_P resolved)
    #   5 — max_iterations (auto-loop limit hit without convergence)
    #
    # IMPORTANT: exit 0 means ONLY converged/nothing_to_do — never a blocked run.
    stopped_by = result.get("stopped_by", "")
    if stopped_by == "fp_dispatch":
        sys.exit(2)
    if stopped_by == "fh_gate":
        sys.exit(3)
    if stopped_by == "fd_gap":
        sys.exit(4)
    if stopped_by == "max_iterations":
        sys.exit(5)


if __name__ == "__main__":
    main()
