# LoanSphere — Design System Spec

This document defines the visual language for the entire LoanSphere platform.
Every page — existing and new — must follow this spec. Paste this file into
Antigravity once at the start of a session, then reference it in every
subsequent feature prompt with: "Follow SPEC_DESIGN_SYSTEM.md for all styling."

---

## 1. Layout Shell

Every authenticated page (everything except login/register) uses the same
two-column shell: a fixed left sidebar + a scrollable main content area.
No page should build its own custom layout or navigation.

```
┌─────────────┬──────────────────────────────────────┐
│             │                                      │
│  Sidebar    │           Main content area          │
│  (fixed)    │           (scrollable)                │
│  180px      │                                      │
│             │                                      │
└─────────────┴──────────────────────────────────────┘
```

### Sidebar structure (top to bottom)

1. **Logo** — "LoanSphere" text, bold, 15px, top padding
2. **Nav items** (in this exact order):
   - Dashboard (icon: `ti-home`)
   - Loan Tools (icon: `ti-file-text`) — expands to Summarizer / Extractor / Chatbot / Bank Forms
   - KYC (icon: `ti-shield-check`)
   - Credit Score (icon: `ti-chart-bar`)
   - Loan Advisor (icon: `ti-scale`)
3. **Spacer** — pushes remaining items to bottom
4. **Profile** (icon: `ti-user`) — pinned to bottom of sidebar

### Nav item states

- **Default**: gray text (`--text-secondary`), no background
- **Active/current page**: light blue background (`--bg-accent-muted`), blue text (`--text-accent`), font-weight 500
- **Hover**: subtle background (`--surface-1`)

Each nav item is a flex row: icon (16px) + label (13px), 8px gap, 8px padding, `var(--radius)` corner radius.

---

## 2. Color Usage Rules

Color must always carry meaning — never decorative. Use this exact mapping
across the whole app:

| Color | Use for | Never use for |
|-------|---------|----------------|
| **Blue** (`accent`) | Primary actions, active nav state, links, the one featured/recommended card per page | Status indicators, decorative accents |
| **Green** (`success`) | KYC verified, loan approved, positive verdict, high credit score band | Any non-status content |
| **Amber** (`warning`) | KYC pending, credit score in review band, borderline FOIR, "needs attention" states | Errors or failures |
| **Red** (`danger`) | KYC rejected, loan rejected, low credit score band, form validation errors | Warnings or pending states |
| **Gray** (`text-secondary` / `text-muted`) | All supporting text, labels, metadata, inactive nav items | Primary content or headings |

**Rule of thumb**: one accent color (blue) drives interaction. Green/amber/red
are reserved strictly for status — a user should be able to tell the state of
something (verified/pending/rejected) from color alone, consistently, on
every page.

---

## 3. Component Patterns

### 3.1 Metric card (dashboard summary numbers)

Used for at-a-glance stats — KYC status, credit score, document count, etc.

- Background: `var(--surface-1)`
- No border
- Border radius: `var(--radius)`
- Padding: `1rem`
- Label: 13px, `var(--text-secondary)`, positioned above the value
- Value: 15–24px, font-weight 500, `var(--text-primary)` (or a status color if
  representing a status)
- Arrange in a grid of 3–4 columns with `12px` gap

### 3.2 Feature card (tool/navigation cards)

Used on the dashboard to link into each tool (Summarizer, Extractor, Chatbot,
Bank Forms, KYC, Credit Score, Loan Advisor).

- Background: `var(--surface-2)`
- Border: `0.5px solid var(--border)` (default) or `2px solid var(--border-accent)`
  for exactly one featured/recommended card per page
- Border radius: `12px`
- Padding: `1rem`
- Layout: leading Tabler icon (20px, colored `var(--text-accent)`) + title
  (14px, font-weight 500) + one-line description (12px, `var(--text-secondary)`)
- Arrange in a 2-column grid with `12px` gap

### 3.3 Status badge

Used for KYC status, loan verdict, credit score band — anywhere a state needs
a compact visual label.

- Background: `var(--bg-{role})` where role is `success` / `warning` / `danger`
- Text color: `var(--text-{role})` — matching role
- Padding: `4px 12px`
- Border radius: `var(--radius)`
- Font size: 12px, font-weight 500
- Text: sentence case, no punctuation ("Verified", "Pending", "Rejected" —
  not "VERIFIED" or "Verified.")

### 3.4 Form fields

- All inputs, selects, textareas: 36px height, `var(--fill-field)` background,
  `var(--fill-field-ring)` border, focus ring on `:focus`
- Labels: 13px, `var(--text-secondary)`, positioned above the field, 4px gap
- Group related fields into sections with a 15px font-weight 500 section
  header (e.g. "Personal details", "Employment details")
- Required field indicator: small red asterisk after the label text

### 3.5 Buttons

- Primary action (submit, generate, verify): filled blue background,
  `var(--on-accent)` text — **only one primary button per page/section**
- Secondary actions (cancel, back, download): outline style, transparent
  background, `var(--border-strong)` border
- Destructive actions (delete, reject): red outline or filled per severity
- Button text: verb-first, sentence case, no punctuation — "Verify KYC",
  "Generate score", "Download form" (not "Submit" or "Click Here")

---

## 4. Typography

- Font: system default sans-serif (no custom font imports)
- Page title (top of main content): 20px, font-weight 500
- Section headers: 15px, font-weight 500
- Body text: 14px, font-weight 400
- Supporting/meta text: 13px, `var(--text-secondary)`
- Micro text (badges, tags): 12px
- **Sentence case everywhere** — never Title Case or ALL CAPS, including
  buttons, nav items, headers, and badge text
- No terminal punctuation on labels, headings, or button text

---

## 5. Spacing

- Page padding (main content area): `1.25rem 1.5rem`
- Section vertical spacing: `20px` between major sections
- Card internal padding: `1rem`
- Grid gaps: `12px` for card grids, `12px` for form field groups
- Sidebar item padding: `8px`

---

## 6. Icons

Use Tabler outline icons exclusively (`<i class="ti ti-{name}">`), sized
16px inline / 20px for feature card leads / 24px max decorative. Never use
filled variants or hand-drawn SVG icons.

**Icon reference for this app:**

| Section | Icon |
|---------|------|
| Dashboard | `ti-home` |
| Loan Tools | `ti-file-text` |
| Summarizer | `ti-file-search` |
| Extractor | `ti-tags` |
| Chatbot | `ti-message-circle` |
| Bank Forms | `ti-building-bank` |
| KYC | `ti-shield-check` |
| Credit Score | `ti-chart-bar` |
| Loan Advisor | `ti-scale` |
| Profile | `ti-user` |
| Upload | `ti-upload` |
| Download | `ti-download` |
| Verified status | `ti-check` |
| Pending status | `ti-clock` |
| Rejected status | `ti-x` |

---

## 7. What NOT to do

- No gradients, drop shadows, glow, or neon effects anywhere
- No dark/colored page backgrounds — pages stay on light neutral surfaces
- No custom per-page navigation — always reuse the sidebar shell
- No more than one primary (blue filled) button visible at a time
- No color used decoratively — every color must map to the rules in Section 2
- No emoji in the UI — use Tabler icons instead
- No Title Case or ALL CAPS text anywhere in the interface

---

## 8. Instruction for Antigravity

> When building any new page for LoanSphere, always wrap the page content in
> the shared sidebar shell described in Section 1. Reuse the same sidebar
> component/include across all pages rather than duplicating markup. Apply
> the color, spacing, typography, and component rules in this document
> exactly as specified. If a new UI element is needed that isn't covered
> here, default to the flattest, most minimal version consistent with the
> existing style — light surfaces, thin borders, no shadows, no gradients.
