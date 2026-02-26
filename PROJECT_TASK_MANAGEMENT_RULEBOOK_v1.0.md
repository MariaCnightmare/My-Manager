# PROJECT TASK MANAGEMENT RULEBOOK v1.0

Generated: 2026-02-26

------------------------------------------------------------------------

# 0. PURPOSE

This document defines the complete operational rules for task
management, progress tracking, logging, and project suspension for all
personal development projects.

Goal: - Eliminate ambiguity - Prevent psychological backlog - Maintain
restartability - Standardize decision-making

This file is the single authoritative reference.

------------------------------------------------------------------------

# 1. SINGLE SOURCE OF TRUTH

All official records must exist only in:

-   GitHub Issues (tasks)
-   GitHub Projects (status board)
-   WEEKLY.md (weekly summary)
-   TASK_SYSTEM.md (this rulebook)

No task exists unless it exists as an Issue.

------------------------------------------------------------------------

# 2. PROJECT STRUCTURE RULES

## 2.1 Hierarchy

L1: Epic (Outcome Level) - 1--2 weeks meaningful result - Produces
working output - Must be measurable

L2: Story (Functional Unit) - Delivers working feature - No
"design-only" closure

L3: Task (Issue Level) - 90 minutes to half-day - Atomic - Clear
completion criteria

------------------------------------------------------------------------

# 3. TASK TYPES (STRICTLY LIMITED TO FOUR)

Every Issue must be one of:

-   Investigate
-   Decide
-   Implement
-   Verify

No additional types allowed.

------------------------------------------------------------------------

# 4. ISSUE FORMAT RULES

## 4.1 Title Format

\[type\] concise description

Examples: \[Investigate\] SVG dashed path behavior \[Implement\] Support
cutDashedPaths\[\] \[Verify\] Confirm PDF 2-page export

------------------------------------------------------------------------

## 4.2 Mandatory Issue Template

### Purpose (Why)

Explain the reason.

### Definition of Done

-   [ ] Condition 1
-   [ ] Condition 2
-   [ ] Verified working

### Not In Scope

Clarify exclusions.

### Plan (Max 3 lines)

1.  
2.  
3.  

### Dependencies

Blocked by: Blocks:

------------------------------------------------------------------------

# 5. LOGGING RULES (MANDATORY)

Every work session must leave a comment using ONLY:

-   ✅ Done:
-   🔎 Found:
-   🧱 Blocked:
-   ⏭ Next:

Blocked entries MUST include next attempt.

------------------------------------------------------------------------

# 6. PROJECT BOARD STRUCTURE (FIXED)

Columns are permanently:

1.  Inbox
2.  Ready
3.  Doing (Max 2)
4.  Blocked
5.  Done

Rules: - WIP limit = 2 - No silent blocking - Doing requires DoD written

------------------------------------------------------------------------

# 7. STOPPING A PROJECT (CONTROLLED SUSPENSION)

To stop a project:

1.  Move all active issues to Blocked
2.  Add one-line stop reason
3.  Add restart condition

Example:

Stop reason: SVG spec unstable

Restart condition: Template finalized

------------------------------------------------------------------------

# 8. WEEKLY REVIEW FORMAT (WEEKLY.md)

## YYYY-MM-DD

## \### Top 3 Completed

-   
-   

## \### Key Findings

## \### Blockers

## \### Next Week First Actions

-   
-   

### Suspended Projects

-   Name: reason

------------------------------------------------------------------------

# 9. PRIORITY RULES

Priority labels: - P1 Critical - P2 Important - P3 Optional

No more than: - 1 P1 at a time - 2 items in Doing

------------------------------------------------------------------------

# 10. DECISION FREEZE RULE

Once Decide task is marked Done: - Decision is frozen - No silent
change - Reversal requires new Decide issue

------------------------------------------------------------------------

# 11. SCOPE CONTROL RULE

If task grows beyond half-day: - Split immediately - Do not continue
expanding

------------------------------------------------------------------------

# 12. RESTART PROTOCOL

When returning after pause:

1.  Open Project board
2.  Read Blocked column
3.  Read latest ⏭ Next comment
4.  Start with smallest atomic task

------------------------------------------------------------------------

# 13. ANTI-CHAOS PRINCIPLES

-   No vague tasks
-   No parallel overextension
-   No undocumented blocking
-   No mental-only tracking

------------------------------------------------------------------------

# 14. SYSTEM GOAL

This system exists to:

-   Maintain clarity
-   Reduce friction
-   Enable restartability
-   Remove psychological weight
-   Make progress visible

------------------------------------------------------------------------

END OF RULEBOOK
