---
status: complete
phase: 44-analyst-feedback-loop
source: [44-01-SUMMARY.md, 44-02-SUMMARY.md, 44-03-SUMMARY.md, 44-04-SUMMARY.md]
started: 2026-04-12T00:00:00Z
updated: 2026-04-12T00:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running backend/dashboard processes. Start the backend fresh (uv run python -m backend.main or equivalent). The server boots without errors, FeedbackClassifier initializes in lifespan, feedback_verdicts Chroma collection is created, and GET /api/health returns 200.
result: pass

### 2. TP/FP Verdict Buttons in Expanded Row
expected: Open DetectionsView. Click to expand any detection row. In the expanded panel (below event details), two ghost-style buttons appear side by side: [ ✓ True Positive ] and [ ✗ False Positive ]. They appear for both correlation detections and CAR/sigma detections.
result: pass

### 3. Toast Notification + Button Highlight on Submit
expected: In an expanded detection row, click [ ✓ True Positive ]. The TP button highlights green immediately. A brief toast notification appears ("Marked as True Positive") and disappears after ~3 seconds without any page action needed.
result: pass

### 4. Verdict Badge on Collapsed Row
expected: After submitting a TP verdict and collapsing the row, a small green "TP" badge appears on the collapsed row (in the rule-name cell or beside it). Rows without a verdict show no badge.
result: pass

### 5. Verdict is Reversible
expected: On a row that already shows a TP badge, expand the row. The TP button is highlighted green. Click [ ✗ False Positive ]. The FP button highlights red, TP highlight clears, a "Marked as False Positive" toast fires, and the collapsed row badge changes to red "FP".
result: pass

### 6. Unreviewed Filter Chip
expected: In DetectionsView filter chips row (CORR / ANOMALY / SIGMA), an "Unreviewed" chip is present. Click it — rows that already have a TP or FP verdict disappear, leaving only un-verdicted detections visible. Clicking it again restores all rows.
result: pass

### 7. Similar Confirmed Cases in InvestigationView
expected: First submit at least one verdict on any detection. Then open InvestigationView for any detection. Scroll below the CAR analytics / investigation summary. If Chroma found similar cases, a "Similar Confirmed Cases" section appears showing up to 3 cards, each with: rule name, TP/FP verdict badge, similarity percentage, and a short event summary. If no similar cases exist, the section is absent (no empty state shown).
result: pass

### 8. Feedback KPI Tiles in OverviewView
expected: Navigate to OverviewView. Below (or alongside) the existing KPI cards, four new tiles are visible: "Verdicts Given" (integer count), "TP Rate" (percentage), "FP Rate" (percentage), and "Training Samples" (integer). All show 0 or actual values depending on submitted verdicts. No layout breakage on the existing KPI row.
result: pass

### 9. Classifier Accuracy Gated at ≥10 Verdicts
expected: While Training Samples count is below 10, the "Classifier Accuracy" tile does NOT appear in OverviewView. Once at least 10 verdicts have been submitted (requires testing with real or seeded verdicts), the Classifier Accuracy tile appears showing a percentage. (Skip this test if you can't easily generate 10 verdicts — mark as skip.)
result: pass

## Summary

total: 9
passed: 9
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
