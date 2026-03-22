"""
genesis_chat — project spec as GTL Package

A channel where human and multiple AI agents coordinate software construction
using genesis workflows. The GTL F_D→F_P→F_H escalation chain governs both
channel dispatch (routing messages) and the work itself (running iterations).

Profile: spike
Graph: intent → requirements → feature_decomp → design → code ↔ unit_tests

genesis_chat depends on abiogenesis and genesis_sdlc. Run engine as:
    PYTHONPATH=.genesis python -m genesis <command> --workspace .
"""
from gtl.core import (
    Package, Asset, Edge, Operator, Rule, Context, Evaluator, Job, Worker,
    F_D, F_P, F_H, consensus,
    OPERATIVE_ON_APPROVED, OPERATIVE_ON_APPROVED_NOT_SUPERSEDED,
)


# ── Contexts ──────────────────────────────────────────────────────────────────

bootloader = Context(
    name="bootloader",
    locator="workspace://gtl_spec/GENESIS_BOOTLOADER.md",
    digest="sha256:" + "0" * 64,
)

this_spec = Context(
    name="genesis_chat_spec",
    locator="workspace://gtl_spec/packages/project_package.py",
    digest="sha256:" + "0" * 64,
)

intent_doc = Context(
    name="intent",
    locator="workspace://INTENT.md",
    digest="sha256:" + "0" * 64,
)

design_adrs = Context(
    name="design_adrs",
    locator="workspace://builds/python/design/adrs/",
    digest="sha256:" + "0" * 64,
)


# ── Operators ─────────────────────────────────────────────────────────────────

claude_agent  = Operator("claude_agent",  F_P, "agent://claude/genesis_chat")
human_gate    = Operator("human_gate",    F_H, "fh://single")
pytest_op     = Operator("pytest",        F_D, "exec://python -m pytest builds/python/tests/ -q -m 'not e2e'")
check_impl_op = Operator("check_impl",    F_D, "exec://python -m genesis check-tags --type implements --path builds/python/src/")
check_test_op = Operator("check_test",    F_D, "exec://python -m genesis check-tags --type validates --path builds/python/tests/")


# ── Rules ─────────────────────────────────────────────────────────────────────

standard_gate = Rule(
    "standard_gate", approve=consensus(1, 1), dissent="recorded"
)


# ── Assets ────────────────────────────────────────────────────────────────────

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
    markov=["adrs_recorded", "tech_stack_decided", "interfaces_specified", "no_implementation_details"],
    operative=OPERATIVE_ON_APPROVED_NOT_SUPERSEDED,
)

code = Asset(
    name="code",
    id_format="CODE-{SEQ}",
    lineage=[design],
    markov=["implements_tags_present", "importable", "no_v2_features"],
)

unit_tests = Asset(
    name="unit_tests",
    id_format="TEST-{SEQ}",
    lineage=[code],
    markov=["all_pass", "validates_tags_present"],
)


# ── Edges ─────────────────────────────────────────────────────────────────────

e_intent_req = Edge(
    name="intent→requirements",
    source=intent,
    target=requirements,
    using=[claude_agent, human_gate],
    rule=standard_gate,
    context=[bootloader, this_spec],
)

e_req_feat = Edge(
    name="requirements→feature_decomp",
    source=requirements,
    target=feature_decomp,
    using=[claude_agent, human_gate],
    rule=standard_gate,
    context=[bootloader, this_spec, intent_doc],
)

e_feat_design = Edge(
    name="feature_decomp→design",
    source=feature_decomp,
    target=design,
    using=[claude_agent, human_gate],
    rule=standard_gate,
    context=[bootloader, this_spec, intent_doc],
)

e_design_code = Edge(
    name="design→code",
    source=design,
    target=code,
    using=[claude_agent, check_impl_op],
    context=[bootloader, this_spec, design_adrs],
)

e_tdd = Edge(
    name="code↔unit_tests",
    source=[code, unit_tests],
    target=unit_tests,
    co_evolve=True,
    using=[claude_agent, pytest_op, check_impl_op, check_test_op],
    context=[bootloader, this_spec, design_adrs],
)


# ── Evaluators ────────────────────────────────────────────────────────────────

# intent→requirements
eval_intent_fh = Evaluator(
    "intent_approved", F_H,
    "Human confirms: problem is clearly stated, value proposition is evident, scope is bounded",
)

# requirements→feature_decomp
eval_req_coverage = Evaluator(
    "req_coverage", F_D,
    "Every REQ key in Package.requirements appears in ≥1 feature vector satisfies: field",
    command="python -m genesis check-req-coverage --package gtl_spec.packages.project_package:package --features .ai-workspace/features/",
)
eval_decomp_fp = Evaluator(
    "decomp_complete", F_P,
    "Construct feature vectors for all uncovered REQ keys — write one .yml per feature to "
    ".ai-workspace/features/active/ with a satisfies: list covering the assigned REQ-F-* keys. "
    "Group related keys into cohesive features. Each vector must cover at least one uncovered key.",
)
eval_decomp_fh = Evaluator(
    "decomp_approved", F_H,
    "Human approves: feature set is complete, dependency order is correct, MVP boundary is clear",
)

# feature_decomp→design
eval_design_fp = Evaluator(
    "design_coherent", F_P,
    "Agent: ADRs cover all features, tech stack is decided, interfaces are specified, "
    "no implementation details have leaked into spec",
)
eval_design_fh = Evaluator(
    "design_approved", F_H,
    "Human approves design before any code is written",
)

# design→code
eval_impl_tags = Evaluator(
    "impl_tags", F_D,
    "All source files carry at least one # Implements: REQ-* tag, zero untagged",
    command="python -m genesis check-tags --type implements --path builds/python/src/",
)
eval_code_fp = Evaluator(
    "code_complete", F_P,
    "Agent: code implements all features per design ADRs; no V2 features present; importable",
)

# code↔unit_tests
eval_tests_pass = Evaluator(
    "tests_pass", F_D,
    "pytest: zero failures, zero errors (excluding e2e tests)",
    command="python -m pytest builds/python/tests/ -q --tb=short -m 'not e2e'",
)
eval_test_tags = Evaluator(
    "validates_tags", F_D,
    "All test files carry at least one # Validates: REQ-* tag, zero untagged",
    command="python -m genesis check-tags --type validates --path builds/python/tests/",
)
eval_coverage_fp = Evaluator(
    "coverage_complete", F_P,
    "Agent: test suite covers all features; no REQ key without a corresponding test",
)


# ── Jobs ──────────────────────────────────────────────────────────────────────

job_intent_req  = Job(e_intent_req,  [eval_intent_fh])
job_req_feat    = Job(e_req_feat,    [eval_req_coverage, eval_decomp_fp, eval_decomp_fh])
job_feat_design = Job(e_feat_design, [eval_design_fp, eval_design_fh])
job_design_code = Job(e_design_code, [eval_impl_tags, eval_code_fp])
job_tdd         = Job(e_tdd,         [eval_tests_pass, eval_test_tags, eval_coverage_fp])


# ── Worker ────────────────────────────────────────────────────────────────────

worker = Worker(
    id="claude_code",
    can_execute=[job_intent_req, job_req_feat, job_feat_design, job_design_code, job_tdd],
)


# ── Package ───────────────────────────────────────────────────────────────────

package = Package(
    name="genesis_chat",
    assets=[intent, requirements, feature_decomp, design, code, unit_tests],
    edges=[e_intent_req, e_req_feat, e_feat_design, e_design_code, e_tdd],
    operators=[claude_agent, human_gate, pytest_op, check_impl_op, check_test_op],
    rules=[standard_gate],
    contexts=[bootloader, this_spec, intent_doc, design_adrs],
    requirements=[
        # Channel substrate
        "REQ-F-CHAN-001",   # EchoAdapter — local CLI channel (stdin/stdout)
        "REQ-F-CHAN-002",   # MessageAdapter interface — platform-agnostic ABC
        "REQ-F-CHAN-003",   # Channel loop — receive, dispatch, respond, repeat
        # Agent registry
        "REQ-F-AGENT-001",  # YAML agent registry — identity, workflow bindings, write territory
        "REQ-F-AGENT-002",  # Agent claim — agent registers intent to work on a feature/edge
        # Message dispatcher
        "REQ-F-DISP-001",   # F_D dispatch — registered commands matched by pattern, no LLM
        "REQ-F-DISP-002",   # F_P dispatch — work intent routed to agent + workflow
        "REQ-F-DISP-003",   # F_H gate — approval prompts surface in channel, human replies
        # Workflow bindings
        "REQ-F-WORK-001",   # gen-start binding — dispatch to genesis start on target project
        "REQ-F-WORK-002",   # gen-iterate binding — dispatch to genesis iterate on target project
        # Context assembly
        "REQ-F-CTX-001",    # Workspace context assembled from event stream + spec for F_P
        # Traceability
        "REQ-F-TRACE-001",  # All agent actions in channel emit events to target project stream
    ],
)


if __name__ == "__main__":
    import json
    print(json.dumps({
        "package": package.name,
        "assets": [a.name for a in package.assets],
        "edges": [e.name for e in package.edges],
        "requirements": package.requirements,
    }, indent=2))
