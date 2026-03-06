# Cashore 4PT: Theory Charter (v2)

This file defines the **conceptual theory only** for Cashore’s Four Problem Types (4PT).
It is intended to help an AI (or human) classify a document into **Type 1, 2, 3, 4**, or **Not Applicable / Uncertain** by using a small number of precise, diagnostic rules.

4PT is a **2×2** classification based on two independent dimensions:

- **Dimension A. Problem-contingent** (problem-solving dominates) vs **Universal / not problem-contingent**.
- **Dimension B. Utility dominates** vs **Utility does not dominate**.

The mapping is fixed:

| | Utility dominates (YES) | Utility dominates (NO) |
|---|---|---|
| Problem-contingent (YES) | **Type 1 (Commons)** | **Type 4 (Prioritization)** |
| Problem-contingent (NO, universal) | **Type 2 (Optimization)** | **Type 3 (Compromise)** |

---

## 0. Universe gate (scope): Is the document in-scope for 4PT coding?

**In-scope ("in-universe")**: The document is doing **policy/governance analysis** or **prescribing governance action**, including institutional design, regulation, policy tool choice, governance mechanisms, program evaluation framed as policy/governance, etc.

**Out-of-scope ("Not Applicable")**: The document is **purely scientific/technical background** about a phenomenon (even a huge crisis) but does **not** identify policy/governance interventions, recommendations, or governance implications.

Rule:
- If there are **no governance/policy prescriptions or implications**, output **Not Applicable**.
- Otherwise continue.

Important warning:
- Many science-heavy documents can look “Type 4-ish” because they discuss catastrophic crises, but if they do not engage policy/governance solutions, they are **Not Applicable**, not Type 4.

---

## 1. Core concept: What counts as an "on-the-ground problem"?

An **on-the-ground problem** is a **substantive, empirically measurable condition or target**, e.g.:
- limiting warming to a specific threshold,
- preventing extinction of a species,
- reducing pollutant concentrations,
- reducing traffic fatalities,
- restoring a fish stock to avoid collapse,
- universal access to a concrete service.

It must be describable as a measurable outcome \(Y\) (even if exact measurement is hard).

### What is NOT an on-the-ground problem by itself
Do not treat these as the “problem” unless the document explicitly ties them to a substantive measurable outcome \(Y\):
- abstract values: "equity", "rights", "legitimacy", "trust", "stakeholder inclusion",
- governance mechanisms: "compliance", "better enforcement", "policy coherence", "coordination", "inspector discretion",
- process quality: "fairness", "participation", "transparency".

**Common failure mode to avoid**:
- Confusing a **policy mechanism** (X) with the **substantive outcome** (Y).
  Example: treating “low compliance” as the main problem when the paper never links compliance to a measurable environmental/health outcome.

---

## 2. Dimension A: Problem-contingent vs Universal

### A1. Problem-contingent (YES) definition
A document is **problem-contingent** if its analysis and conclusions are:
- **generated from, and narrowed to**, understanding/improving/solving a **clearly specified on-the-ground problem (or a class of similar problems)**, and
- oriented toward **how** to solve/manage it (teleological / problem-solving stance), not toward deciding **whether** it should be solved.

Key signature:
- The paper treats the target as something that must be pursued, then asks "how do we achieve it?".

### A2. Universal / not problem-contingent (NO) definition
A document is **universal** (not problem-contingent) if it applies a **pre-established adjudicating framework** intended to evaluate **any policy problem**, enabling deliberation over:
- "how to act", and also
- "whether to act at all", or whether the goal should be relaxed/overridden by broader considerations.

Canonical examples:
- cost-benefit analysis (CBA) / welfare-maximization frameworks that can conclude "do nothing",
- universal preference theories (e.g., general theories of state behavior/preferences),
- universal conflict-resolution / legitimacy frameworks applied as the governing logic.

### Critical clarification: "Problem-contingent" ≠ "not generalizable"
A problem-contingent approach can still generalize to a **class of similar problems**.
The key question is whether the analytic frame is **derived from the problem’s structure** and constrained by that problem, versus being a **general adjudication method**.

---

## 3. Dimension B: Utility dominates vs Utility does not dominate

### B1. Utility dominates (YES) definition
Utility dominates when the document’s analysis assumes or treats actors as largely:
- **self-interested / satisfaction-driven**, and/or
- evaluates policies by **utility, welfare, efficiency, preference satisfaction, profit, national interest**, or similar maximization logic.

Diagnostic test (objective function test):
- If the paper’s core success metric is “maximize aggregate welfare/utility (often monetized)”, utility dominates.

High-confidence cues:
- explicit monetization, discounting, aggregate welfare, efficiency maximization, preference aggregation,
- "net benefits", "maximize social welfare", "optimal policy".

### B2. Utility does not dominate (NO) definition
Utility does not dominate when the governing metric/motivation is **not utility maximization** and instead centers:
- rights/dignity/justice as constraints,
- legitimacy/appropriateness/trust as primary success conditions,
- ecological integrity, non-negotiable thresholds, or "must be achieved" objectives,
- critique of utilitarian/efficiency logic as insufficient or corrupting.

Diagnostic test:
- If the paper treats some outcomes as **incommensurable** with welfare optimization (i.e., not “tradeable” via commensuration), utility does not dominate.

Important trap:
- The presence of the words “efficiency”, “cost”, “incentives”, or “utility” is NOT enough.
  The issue is whether utility is adopted as the governing goal, or is treated as secondary/criticized.

---

## 4. The four Types: operational signatures

### Type 1. Commons = Problem-contingent YES + Utility YES
Definition:
- The document is anchored in solving a specific on-the-ground problem, and the solution is framed in utility-enhancing terms.

Canonical signature:
- collective action / commons collapse framing,
- institutional design to prevent resource collapse and preserve long-term utility (e.g., sustained yield),
- focuses on "how to fix this specific problem", not on whether it should be fixed.

Examples of cues:
- commons, CPR, prisoners’ dilemma, free-riding, compliance to prevent collapse of a specific resource system.

---

### Type 2. Optimization = Problem-contingent NO + Utility YES
Definition:
- The document uses a universal utility-maximization logic to decide policy action; it can conclude that solving the focal problem is not worthwhile.

Canonical signature:
- "consider all tradeoffs; solving X may be suboptimal overall",
- CBA / welfare economics / aggregate utility,
- optimization of preferences (individual, organizational, state), including IR preference frameworks.

High-confidence cues:
- "net benefits", "cost-benefit", "social welfare maximization", monetization of disparate values.

---

### Type 3. Compromise = Problem-contingent NO + Utility NO
Definition:
- The document applies a universal non-utility framework emphasizing legitimacy, inclusion, appropriateness, deliberation, trust, or consensus; success is not defined as achieving a specific on-the-ground target.

Canonical signature:
- multi-stakeholder governance, deliberative democracy, ADR, legitimacy and trust-building,
- balancing among values/interests, accepting compromise outcomes.

High-confidence cues:
- stakeholder inclusion, legitimacy, trust, transparency, accountability, ADR, consensus-building, “good governance”.

---

### Type 4. Prioritization = Problem-contingent YES + Utility NO
Definition:
- The document begins and ends with solving a specified on-the-ground problem **as a non-negotiable priority**, rejecting commensuration that would allow the target to be traded off against utility.

Canonical signature:
- lexical priority / sequentialism: some outcomes must be achieved, other concerns are second-order,
- rejection of CBA/optimization/logrolling when they reopen permissibility.

High-confidence cues:
- "must be achieved", "non-negotiable", threshold/rights-like constraints,
- explicit critique of utility-driven approaches as causes of the problem.

Anchor examples:
- anti-slavery reasoning (no one may own another person),
- preventing extinction, hard ecological thresholds, Paris-style fixed climate objectives (when treated as must-hit constraints).

---

## 5. Highest-priority disambiguation rules (use these first)

### Rule 1. Type 4 vs Type 3 (most common confusion)
Ask: What is the **success criterion**?

- If success is **process quality** (legitimacy, inclusion, trust, appropriateness, consensus), it is **Type 3**.
- If success is **achieving a substantive target that must be achieved**, and process is only instrumental, it is **Type 4**.

Practical test:
- If the paper would accept missing the substantive target as long as the process was legitimate, it is Type 3.
- If missing the target is treated as failure regardless of process legitimacy, it is Type 4.

### Rule 2. Mechanism vs outcome (prevents many Type 4 false positives)
If the paper’s "problem" statement is mainly a governance mechanism (compliance, legitimacy, inspector behavior) and does not anchor to a measurable outcome \(Y\), do NOT code Type 4.
This pattern is usually **Type 3** (process/legitimacy orientation) or **Not Applicable** (if no policy/governance prescriptions).

### Rule 3. Type 1 vs Type 2
Both can use economics and utility language. The key is whether the framework can decide "do nothing" or relax the goal.

- If the target is treated as fixed and the paper asks how to solve it in a utility-oriented way: **Type 1**.
- If the paper applies a universal welfare/utility calculus that could recommend not solving the target: **Type 2**.

### Rule 4. “Cost-effectiveness” vs “Cost-benefit”
- “Cost-benefit” is a strong Type 2 cue (commensuration; could justify inaction).
- “Cost-effectiveness” is ambiguous: it can appear in any Type.
  If it is used **inside a non-negotiable target** ("given we must hit X, minimize cost"), it does not by itself imply Type 2.

---

## 6. Required decision procedure (do this in order)

1. **Universe gate**: In-scope policy/governance analysis? If no, output **Not Applicable**.
2. **Write the paper’s core problem in one sentence**.
   - If you wrote a mechanism (X) instead of a measurable outcome (Y), re-check whether the paper ever defines the substantive target.
3. **Code Dimension A (Problem-contingent vs Universal)** using Section 2.
4. **Code Dimension B (Utility dominates vs not)** using Section 3.
5. **Map to Type** using the fixed 2×2 table.
6. **Ambiguity handling**:
   - If evidence is insufficient or points strongly to multiple quadrants, output **Uncertain** rather than guessing.
   - Do not use elimination logic where Type 3 becomes the “leftover” by default.

---

## 7. What NOT to do (hard prohibitions)

- Do not infer Type from topic domain (e.g., "environmental" ≠ Type 4).
- Do not treat the policy tool or governance mechanism as the on-the-ground problem unless it is explicitly tied to a measurable target.
- Do not rely on keyword shortcuts (“utility”, “efficiency”, “stakeholders”) without checking the governing success criterion and whether the frame is universal or problem-contingent.
