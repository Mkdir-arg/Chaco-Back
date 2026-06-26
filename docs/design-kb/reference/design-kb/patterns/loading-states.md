# Pattern: Loading States
**Source: NODO DS.md (general rules), CHACO_NODO_Design_Manual.md**

---

## Overview

Loading states preserve layout stability and prevent jarring shifts. The system uses skeletons for content areas and inline spinners for button-triggered actions.

---

## Types

### 1. Button Loading State
- **Trigger:** User clicks a Brand or Tertiary button that initiates an async operation
- **Behavior:** Spinner replaces the button label text
- **Rule:** Button width does NOT change during loading
- **Style:** Spinner in the same color as the normal button text (white for Brand, brand color for Tertiary)
- **Disabled:** Button should be disabled during loading to prevent double-submission

### 2. Table / List Skeleton
- **Trigger:** Table data is being fetched
- **Behavior:** Column headers remain visible; rows replaced with skeleton rows
- **Skeleton rows:** Neutral gray animated pulse bars at the approximate width/height of actual content
- **Number of skeleton rows:** Should match the expected page size (e.g., 10 rows)

### 3. Card Skeleton
- **Trigger:** Card data is being fetched
- **Behavior:** Card border and container visible; content replaced with pulse bars
- **Style:** `bg-quaternary` animated pulse matching content zones

### 4. Stat Card Loading
- **Trigger:** Dashboard metrics loading
- **Behavior:** Stat card shape preserved; number and label replaced with skeleton bars

---

## Skeleton Styling

| Element | Value |
|---------|-------|
| Background | `bg-quaternary (#e5e7eb)` |
| Animation | CSS pulse (opacity or shimmer) |
| Border radius | Matches the content it replaces |
| Duration | Loading until data arrives — not time-based |

---

## Rules

- **Never** replace an entire section with a full-page spinner
- **Never** change button size during loading
- **Always** maintain layout structure during loads (skeleton shapes match actual content geometry)
- **Never** show a loading state for less than 200ms — instant responses don't need loading feedback
- **Table loads:** Keep table header visible while rows skeleton-load
- **Form submits:** Disable submit button and show spinner — re-enable only on error, navigate on success
