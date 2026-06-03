# Design Constitution
**NODO — Gobierno del Chaco**
**Highest-Level Principles Governing Every UI Decision**

---

> These are the inviolable laws of the NODO design system.
> When in doubt about any UI decision, return to these principles.
> They take precedence over personal preference, legacy patterns, and convenience.

---

## Article I: Tokens Are Law

**Every color, every size, every spacing value must come from a design token.**

The system has a complete token vocabulary: `--bg-*`, `--border-*`, `--text-*`, `--font-*`, `--rounded-*`. No hex value, no pixel measurement, no color name may be used in a component without a corresponding token.

If a token does not exist for your use case, you must consult the design team before creating a one-off value. Ad-hoc values fragment the system and break dark mode, theming, and future upgrades.

*Exception: The explicit hex values documented in component specifications (button states, badge colors) are permitted because they ARE the token definitions for those components.*

---

## Article II: The Semantic Layer Protects the System

**Never reference primitive color scales directly in components. Always use semantic tokens.**

`bg-brand` is correct. `bg-[#5059bc]` or `color-brand-700` in component code is wrong.

Semantic tokens abstract the color meaning from the color value. When the brand color changes, updating one token updates the entire system. This is why the system was built.

---

## Article III: Dark Mode Is a First-Class Citizen

**Every component must work in both light and dark mode from day one.**

All semantic tokens have light and dark variants. Dark mode is toggled by `data-theme="dark"` or `.dark` on the root element. No component may hardcode a value that only works in light mode.

Building light-mode-only components is technical debt that compounds with every new screen added to the system.

---

## Article IV: Accessibility Is Not Optional

**The system must be usable by all users, regardless of ability.**

- Focus states are always visible — `outline: 2px solid` on focus, never removed
- Color is never the sole communicator of state — labels and icons accompany color
- Interactive elements have accessible labels (aria-label for icon-only buttons)
- Error messages use both color and text to communicate the issue
- WCAG AA contrast ratio must be maintained for all text/background pairs

Disabling focus rings for aesthetic reasons is a system violation, not a style choice.

---

## Article V: One Primary Action Per Context

**Each screen section may have exactly one Brand (gradient) button.**

The visual hierarchy of the system depends on one dominant action being identifiable at a glance. When two Brand buttons exist in the same section, neither is primary — both become noise.

Primary: Brand button. Secondary: Tertiary (outlined brand) or Secondary (neutral outlined).

---

## Article VI: Hierarchy Before Decoration

**Every visual element must earn its place by clarifying hierarchy or communicating meaning.**

The brand gradient exists to mark the single most important action. The `text-heading` color exists to mark primary content. The `text-body-subtle` color exists to mark secondary information.

Decoration that does not serve hierarchy, meaning, or state communication should not exist.

---

## Article VII: Errors Must Be Specific and Actionable

**No user should ever see a generic "Error" message.**

Every error message must:
1. State specifically what went wrong ("El email no es válido")
2. Appear where the error occurred (inline, below the field)
3. Include a visual indicator beyond color alone (icon + text)
4. Never expose internal system details (IDs, stack traces, HTTP codes)

Error messages are written in Spanish, in plain language that a government worker can understand without technical knowledge.

---

## Article VIII: Destructive Actions Must Be Gated

**No irreversible operation may execute without a SweetAlert2 confirmation dialog.**

This is not about distrust of users — it is about the stakes. The system manages citizen data, social programs, and public records. An accidental deletion could have real consequences for real people.

`window.confirm()` is forbidden. The SweetAlert2 modal is the only permitted confirmation mechanism.

---

## Article IX: Structure Before Mobile

**The desktop experience is the primary surface. Mobile is an adaptation.**

NODO is a backoffice for government workers at desks. The sidebar, data tables, stat card grids, and charts are designed for desktop. Mobile adaptations exist and must work, but mobile-first design decisions should not degrade the desktop experience.

---

## Article X: The System Is the Single Source of Truth

**Documentation, tokens, and code are only valid when they agree.**

When a token file (`chaco-tokens.json`), a CSS file (`chaco-tokens.css`), a documentation file (`CHACO_NODO_Design_Manual.md`), and the component code disagree — the most recently updated token file wins.

When documentation conflicts with code, fix the code to match the documented tokens. Exceptions must be documented with a rationale.

---

## Amendment I: CSS Dual-Stack Rule

While the system migrates from Bootstrap/AdminLTE to Tailwind CSS:
- **New templates use Tailwind CSS exclusively**
- **Legacy templates use Bootstrap 5.3.2 + AdminLTE exclusively**
- **Never mix Tailwind and Bootstrap classes in the same component**

This is a transitional state. The long-term goal is Tailwind CSS throughout.

---

## Amendment II: Icon Library Exclusivity

- **New templates: Heroicons (outline default, solid for active states)**
- **Legacy templates: Font Awesome 6.4.0**
- **Never mix icon libraries within the same component**

Both libraries have the same color inheritance rule: icons always use text color tokens, never hardcoded values.
