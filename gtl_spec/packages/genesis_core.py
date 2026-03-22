# Implements: REQ-CORE-001
"""
genesis_core — V1.0 specification as GTL Package

This file IS the spec. The type system is the law.

  Asset.markov     → acceptance criteria for that asset
  Job.evaluators   → convergence tests for that edge
  Edge.context     → constraint surface for that transition
  Worker           → who executes what (write territory by type)

No separate requirements document. REQ keys emerge from this Package.

Built on: imp_codex/code/gtl/core.py v0.3.0
"""
from gtl.core import (
    Package, Asset, Edge, Operator, Rule, Context, Overlay,
    Evaluator, Job, Worker,
    F_D, F_P, F_H, consensus,
    OPERATIVE_ON_APPROVED, OPERATIVE_ON_APPROVED_NOT_SUPERSEDED,
)


# ── Contexts ──────────────────────────────────────────────────────────────────
# Digests are sha256 of the file content at package activation time.
# PENDING = not yet computed — update when file content stabilises.

bootloader = Context(
    name="bootloader",
    locator="workspace://gtl_spec/GENESIS_BOOTLOADER.md",
    digest="sha256:" + "0" * 64,   # PENDING
)

genesis_core_spec = Context(
    name="genesis_core_spec",
    locator="workspace://gtl_spec/packages/genesis_core.py",
    digest="sha256:" + "0" * 64,   # PENDING — self-referential, computed at activation
)

design_adrs = Context(
    name="design_adrs",
    locator="workspace://builds/claude_code/design/adrs/",
    digest="sha256:" + "0" * 64,   # PENDING — computed after ADRs are written
)

v1_doctrine = Context(
    name="v1_doctrine",
    locator="workspace://V1_DOCTRINE.md",
    digest="sha256:" + "0" * 64,   # PENDING
)


# ── Operators ─────────────────────────────────────────────────────────────────

claude_agent = Operator(
    "claude_agent", F_P, "agent://claude/genesis"
)
pytest_op = Operator(
    "pytest", F_D, "exec://python -m pytest builds/claude_code/tests/ -q"
)
check_tags_impl = Operator(
    "check_tags_impl", F_D,
    "exec://python -m genesis check-tags --type implements --path builds/claude_code/code/"
)
check_tags_test = Operator(
    "check_tags_test", F_D,
    "exec://python -m genesis check-tags --type validates --path builds/claude_code/tests/"
)
human_gate = Operator(
    "human_gate", F_H, "fh://single"
)


# ── Rules ─────────────────────────────────────────────────────────────────────

standard_gate = Rule(
    "standard_gate", approve=consensus(1, 1), dissent="recorded"
)


# ── Assets ────────────────────────────────────────────────────────────────────
# markov conditions ARE the acceptance criteria.

intent = Asset(
    name="intent",
    id_format="INT-{SEQ}",
    markov=["problem_stated", "value_proposition_clear", "scope_bounded"],
)

requirements = Asset(
    name="requirements",
    id_format="REQ-{SEQ}",
    lineage=[intent],
    markov=["keys_testable", "intent_covered", "no_implementation_details"],
    operative=OPERATIVE_ON_APPROVED,
)

feature_decomp = Asset(
    name="feature_decomp",
    id_format="FD-{SEQ}",
    lineage=[requirements],
    markov=["all_req_keys_covered", "dependency_dag_acyclic", "mvp_boundary_defined"],
    operative=OPERATIVE_ON_APPROVED,
)

design = Asset(
    name="design",
    id_format="DES-{SEQ}",
    lineage=[feature_decomp],
    markov=[
        "adrs_recorded",
        "six_core_functions_specified",
        "bind_fd_fp_split_specified",
        "precomputed_manifest_specified",
        "scope_type_specified",
    ],
    operative=OPERATIVE_ON_APPROVED_NOT_SUPERSEDED,
)

code = Asset(
    name="code",
    id_format="CODE-{SEQ}",
    lineage=[design],
    markov=[
        "implements_tags_present",
        "six_modules_only",
        "no_v2_features",
        "importable",
    ],
)

unit_tests = Asset(
    name="unit_tests",
    id_format="TEST-{SEQ}",
    lineage=[code],
    markov=[
        "all_pass",
        "coverage_gte_80",
        "validates_tags_present",
        "sandbox_e2e_pass",
    ],
)


# ── Edges ─────────────────────────────────────────────────────────────────────

e_intent_req = Edge(
    name="intent→requirements",
    source=intent,
    target=requirements,
    using=[claude_agent, human_gate],
    rule=standard_gate,
    context=[bootloader, v1_doctrine],
)

e_req_feat = Edge(
    name="requirements→feature_decomp",
    source=requirements,
    target=feature_decomp,
    using=[claude_agent, human_gate],
    rule=standard_gate,
    context=[bootloader, genesis_core_spec],
)

e_feat_design = Edge(
    name="feature_decomp→design",
    source=feature_decomp,
    target=design,
    using=[claude_agent, human_gate],
    rule=standard_gate,
    context=[bootloader, genesis_core_spec, v1_doctrine],
)

e_design_code = Edge(
    name="design→code",
    source=design,
    target=code,
    using=[claude_agent, check_tags_impl],
    context=[bootloader, genesis_core_spec, design_adrs],
)

e_tdd = Edge(
    name="code↔unit_tests",
    source=[code, unit_tests],
    target=unit_tests,
    co_evolve=True,
    using=[claude_agent, pytest_op, check_tags_impl, check_tags_test],
    context=[bootloader, genesis_core_spec, design_adrs],
)


# ── Evaluators ────────────────────────────────────────────────────────────────

# intent→requirements
eval_intent_fh     = Evaluator("intent_approved",    F_H, "Human confirms intent is clear, bounded, and non-trivial")

# requirements→feature_decomp
eval_feat_fd       = Evaluator("req_coverage",       F_D, "Every REQ key appears in ≥1 feature vector satisfies: field",
                               command="python -m genesis check-req-coverage --package gtl_spec.packages.genesis_core:genesis_v1 --features .ai-workspace/features/")
eval_feat_fh       = Evaluator("feat_approved",      F_H, "Human approves decomposition, DAG order, and MVP boundary")

# feature_decomp→design
eval_design_fp     = Evaluator("design_complete",    F_P, "Agent: ADRs specify all 6 functions, bind split, scope type, manifest structure")
eval_design_fh     = Evaluator("design_approved",    F_H, "Human approves design before any code is written")

# design→code
eval_code_tags     = Evaluator("impl_tags",          F_D, "check-tags: all code files carry Implements: REQ-* tags, 0 untagged",
                               command="python -m genesis check-tags --type implements --path builds/claude_code/code/")
eval_six_modules   = Evaluator("six_modules",        F_D, "exactly 6 modules: core, bind, schedule, manifest, commands, __main__",
                               command="python -c \"import os,sys; p='builds/claude_code/code/genesis'; m={f[:-3] for f in os.listdir(p) if f.endswith('.py') and f!='__init__.py'}; e={'core','bind','schedule','manifest','commands','__main__'}; diff=m^e; print('extra:',m-e,'missing:',e-m) if diff else print('OK'); sys.exit(0 if not diff else 1)\"")
eval_code_fp       = Evaluator("code_complete",      F_P, "Agent: code implements all 6 functions per design ADRs; no V2 features present")

# code↔unit_tests
eval_tests_pass    = Evaluator("tests_pass",         F_D, "pytest: 0 failures, 0 errors",
                               command="python -m pytest builds/claude_code/tests/ -q --tb=short --ignore=builds/claude_code/tests/test_e2e_sandbox.py")
eval_coverage      = Evaluator("coverage_80",        F_D, "coverage >= 80%",
                               command="python -m pytest builds/claude_code/tests/ --cov=genesis --cov-report=term-missing -q --ignore=builds/claude_code/tests/test_e2e_sandbox.py")
eval_test_tags     = Evaluator("validates_tags",     F_D, "check-tags: all test files carry Validates: REQ-* tags, 0 untagged",
                               command="python -m genesis check-tags --type validates --path builds/claude_code/tests/")
eval_sandbox_e2e   = Evaluator("sandbox_e2e",        F_D, "sandbox lifecycle: gen_gaps/iterate/converge in a fresh isolated workspace",
                               command="python -m pytest builds/claude_code/tests/test_e2e_sandbox.py -m 'e2e and not phase_c' -q --tb=short")


# ── Jobs ──────────────────────────────────────────────────────────────────────

job_intent_req  = Job(e_intent_req,  [eval_intent_fh])
job_req_feat    = Job(e_req_feat,    [eval_feat_fd, eval_feat_fh])
job_feat_design = Job(e_feat_design, [eval_design_fp, eval_design_fh])
job_design_code = Job(e_design_code, [eval_code_tags, eval_six_modules, eval_code_fp])
job_tdd         = Job(e_tdd,         [eval_tests_pass, eval_coverage, eval_test_tags, eval_sandbox_e2e])


# ── Worker ────────────────────────────────────────────────────────────────────
# Single worker for V1. conflicts_with() trivially false.
# writable_types = {requirements, feature_decomp, design, code, unit_tests}

worker_claude_code = Worker(
    id="claude_code",
    can_execute=[job_intent_req, job_req_feat, job_feat_design, job_design_code, job_tdd],
)


# ── Package ───────────────────────────────────────────────────────────────────

genesis_v1 = Package(
    name="genesis_v1",
    assets=[intent, requirements, feature_decomp, design, code, unit_tests],
    edges=[e_intent_req, e_req_feat, e_feat_design, e_design_code, e_tdd],
    operators=[claude_agent, pytest_op, check_tags_impl, check_tags_test, human_gate],
    rules=[standard_gate],
    contexts=[bootloader, genesis_core_spec, design_adrs, v1_doctrine],
    requirements=[
        # Core engine
        "REQ-F-CORE-001",
        "REQ-F-CORE-002",
        "REQ-F-CORE-003",
        "REQ-F-CORE-004",
        "REQ-F-CORE-005",
        "REQ-F-CORE-006",
        # Commands
        "REQ-F-CMD-001",
        "REQ-F-CMD-002",
        "REQ-F-CMD-003",
        # Workspace
        "REQ-F-WKSP-001",
        "REQ-F-WKSP-002",
        # Non-functional
        "REQ-NFR-TEST-001",
        "REQ-NFR-E2E-001",
        "REQ-NFR-SELF-001",
    ],
)


if __name__ == "__main__":
    print(genesis_v1.describe())
    print()
    print(f"Worker: {worker_claude_code.id}")
    print(f"  writable: {worker_claude_code.writable_types}")
    print(f"  readable: {worker_claude_code.readable_types}")
    print(f"  jobs: {len(worker_claude_code.can_execute)}")
