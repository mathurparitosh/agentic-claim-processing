# Visual Design Theme — "Coffee Shop Admin Dashboard"

Extracted 2026-08-30 from <https://append-teal-34549072.figma.site/> (a Figma Make
site — the design ships as a compiled React + Tailwind v4 app). This file is the
reference for restyling this project's frontend; nothing here is wired in yet.

## Aesthetic in one line

Warm, cozy, modern admin dashboard: **cream paper background, espresso-brown text,
latte-brown as the single accent**, soft 12–16px rounded corners, gentle brown-tinted
shadows, generous spacing, Inter throughout, small uppercase tracked labels. Elevated
and friendly — not flat, not brutalist. Cards lift slightly on hover.

---

## 1. Color palette

### Brand ramp (the only "real" colors)

| Token | Hex | Role |
|---|---|---|
| `--cream` | `#f8f6f2` | app background / paper |
| `--espresso` | `#3e2c1c` | primary text, headings, icons |
| `--warm-taupe` | `#78675c` | secondary / muted text |
| `--latte-brown` | `#a9744f` | **primary accent** — buttons, links, active state, focus ring |
| `--terracotta` | `#d1654b` | destructive / danger / error |
| `--sage-green` | `#6aa57d` | success |
| `--soft-blue` | `#89b8dd` | info / 3rd chart series only |

### Semantic tokens (light)

```
--background:            var(--cream)      /* #f8f6f2 */
--foreground:            var(--espresso)   /* #3e2c1c */
--card:                  #ffffff
--card-foreground:       var(--espresso)
--popover:               #ffffff
--popover-foreground:    var(--espresso)
--primary:               var(--latte-brown)
--primary-foreground:    #ffffff
--secondary:             var(--warm-taupe)
--secondary-foreground:  #ffffff
--muted:                 #f5f3ef            /* slightly warmer than cream, for hover fills / muted panels */
--muted-foreground:      var(--warm-taupe)
--accent:                var(--latte-brown)
--accent-foreground:     #ffffff
--destructive:           var(--terracotta)
--destructive-foreground:#ffffff
--success:               var(--sage-green)
--success-foreground:    #ffffff
--border:                #3e2c1c1a          /* espresso @ ~10% — the ONLY border color anywhere */
--input:                 transparent        /* input border uses --border */
--input-background:       #ffffff
--switch-background:      #cbced4
--ring:                  var(--latte-brown) /* focus outline */
```

### Chart series

`--chart-1..5` = latte-brown, sage-green, soft-blue, terracotta, warm-taupe (in order).

### Dark theme (`.dark` on `<html>`)

```
--background: #3e2c1c   (espresso)      --foreground: #f8f6f2 (cream)
--card / --popover: #4a3429             --card-foreground: cream
--muted: #5a453a                        --muted-foreground: #b5a598
--border: #f8f6f21a  (cream @ ~10%)     --input: #5a453a
--primary / --accent / --ring: #a9744f  (unchanged — latte-brown works on both)
--destructive: #d1654b  --success stays sage
```
Sidebar in dark: `--sidebar: #4a3429`, `--sidebar-accent: #5a453a`.

---

## 2. Typography

- **Font family:** `Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`
  (Inter loaded from Google Fonts, weights 400/500/600/700). Mono: system mono stack.
- **Base:** `--font-size: 14px`; body text `0.875rem` / weight 400 / line-height 1.5.
- **Weights:** normal 400, medium 500, semibold 600, bold 700.

| Element | Size | Weight | Line-height | Color | Notes |
|---|---|---|---|---|---|
| `h1` | `2rem` (`--text-h1`) | 700 | 1.25 | espresso | |
| `h2` | `1.5rem` (`--text-h2`) | 600 | 1.3 | espresso | |
| `h3` | `1.125rem` | 600 | 1.4 | espresso | |
| `h4` | `1rem` | 500 | 1.4 | espresso | |
| `p` / body | `0.875rem` (`--text-body`) | 400 | 1.6 | espresso | |
| `label` | `0.75rem` (`--text-label`) | 500 | 1.4 | **warm-taupe** | `text-transform: uppercase; letter-spacing: 0.025em` |
| `button` text | `0.875rem` | 500 | 1.4 | | |
| `input` text | `0.875rem` | 400 | 1.4 | | |

Utility scale present: `text-xs .75 / sm .875 / base 1 / lg 1.125 / xl 1.25 / 2xl 1.5 / 3xl 1.875`.
Common in the UI: stat values `text-2xl font-bold`, section titles `text-lg font-semibold`,
metadata `text-xs text-coffee-secondary`. Tracking: `tight -0.025em`, `widest 0.1em`.

---

## 3. Radius

`--radius: 0.75rem` (12px) with the shadcn derivative scale:

| Name | Value | ≈ | Used for |
|---|---|---|---|
| sm | `radius - 4px` | 8px | small controls, chips |
| md | `radius - 2px` | 10px | inputs, menu items |
| lg | `radius` | 12px | cards (inline `borderRadius:"12px"` seen) |
| xl | `radius + 4px` | 16px | **default for cards, buttons, icon tiles, inputs, search bar** |
| full | `9999px` | — | avatars, notification badges, status dots |

The UI leans on `rounded-xl` (16px) almost everywhere — it's the signature.

---

## 4. Elevation / shadows

Two brown-tinted shadows only (espresso `#3e2c1c` at low alpha — never neutral gray):

```
--shadow-coffee:     0 2px 8px  #3e2c1c14, 0 1px 3px  #3e2c1c0f;   /* resting cards, header */
--shadow-coffee-lg:  0 4px 16px #3e2c1c1a, 0 2px 6px  #3e2c1c14;   /* hover, sidebar, dropdowns, popovers */
```
Inline equivalent seen: `boxShadow: "0 4px 16px rgba(62, 44, 28, 0.1)"`.

---

## 5. Spacing & layout

- Spacing unit `0.25rem`; the app uses `gap-3` (12px), `gap-6` (24px), `p-4` (16px),
  `p-6` (24px), `mb-8` (32px) most.
- **Fixed left sidebar** `w-64` (256px), white, `border-r border-coffee`, `shadow-coffee-lg`.
  Content and header are offset with `ml-64`.
- **Sticky top header** `sticky top-0 z-20`, white, `border-b border-coffee`, `shadow-coffee`,
  `px-6 py-4`.
- Main content grids: `grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6`.
- Container helpers: `--container-sm 24rem`, `--container-lg 32rem`; `mx-auto` centering.
- Transitions: `transition-all duration-300` on cards; default `0.15s cubic-bezier(.4,0,.2,1)`.

---

## 6. Component patterns (from the compiled markup)

**Card**
`bg-white border border-coffee shadow-coffee rounded-xl` — on interactive cards add
`hover:shadow-coffee-lg hover:-translate-y-1 transition-all duration-300 cursor-pointer`.

**Stat card** (the dashboard's hero unit)
```
card
  ├─ icon tile: w-12 h-12 bg-coffee-cream rounded-xl grid place-items-center  (icon: w-6 h-6 text-coffee-primary)
  ├─ value:  text-2xl font-bold  (espresso)
  ├─ label:  text-sm font-medium (espresso)
  └─ sub:    text-xs text-coffee-secondary   (often a trend delta)
```

**Icon / logo tile**
`w-10 h-10 bg-coffee-primary rounded-xl grid place-items-center` with `text-white font-bold`.

**Button** (primary)
latte-brown fill, white text, `rounded-xl`, `text-sm font-medium`, `px-4 py-2`-ish,
hover ≈ `bg-primary/90`. Ghost/icon button: `p-2 rounded-xl hover:bg-coffee-cream`.

**Input / search**
`bg-input-background (#fff) border border-coffee rounded-xl text-sm`, leading icon
absolutely positioned `left-3 top-1/2 -translate-y-1/2 text-coffee-secondary w-4 h-4`,
field gets `pl-10`.

**Badge / pill**
Small, `text-xs`, rounded-full or rounded-md. Status/notification badge:
`bg-coffee-danger text-white` mini circle `w-5 h-5` pinned `-top-1 -right-1`.
Soft-tint variants use the Tailwind default 100/200/600–800 ramps
(`bg-green-100 text-green-800 border-green-200`, same for red/orange/yellow/blue) —
these are the pale status chips.

**Dropdown / popover**
`bg-white border border-coffee shadow-coffee-lg rounded-xl`, danger items
`text-coffee-danger`.

**Avatar**
`w-8 h-8 rounded-full bg-coffee-primary text-white text-sm font-medium` (initials).

**Charts** — Recharts, using `--chart-1..5`.

---

## 7. Drop-in token block

```css
:root {
  /* brand */
  --cream: #f8f6f2;
  --espresso: #3e2c1c;
  --warm-taupe: #78675c;
  --latte-brown: #a9744f;
  --terracotta: #d1654b;
  --sage-green: #6aa57d;
  --soft-blue: #89b8dd;

  /* semantic */
  --background: var(--cream);
  --foreground: var(--espresso);
  --card: #ffffff;
  --card-foreground: var(--espresso);
  --popover: #ffffff;
  --popover-foreground: var(--espresso);
  --primary: var(--latte-brown);
  --primary-foreground: #ffffff;
  --secondary: var(--warm-taupe);
  --secondary-foreground: #ffffff;
  --muted: #f5f3ef;
  --muted-foreground: var(--warm-taupe);
  --accent: var(--latte-brown);
  --accent-foreground: #ffffff;
  --destructive: var(--terracotta);
  --destructive-foreground: #ffffff;
  --success: var(--sage-green);
  --success-foreground: #ffffff;
  --border: rgba(62, 44, 28, 0.10);
  --input-background: #ffffff;
  --ring: var(--latte-brown);

  --chart-1: var(--latte-brown);
  --chart-2: var(--sage-green);
  --chart-3: var(--soft-blue);
  --chart-4: var(--terracotta);
  --chart-5: var(--warm-taupe);

  /* type */
  --font-sans: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  --font-size-base: 14px;
  --text-h1: 2rem;
  --text-h2: 1.5rem;
  --text-h3: 1.125rem;
  --text-body: 0.875rem;
  --text-label: 0.75rem;
  --weight-normal: 400;
  --weight-medium: 500;
  --weight-semibold: 600;
  --weight-bold: 700;

  /* shape & depth */
  --radius: 0.75rem;            /* 12px */
  --radius-sm: calc(var(--radius) - 4px);
  --radius-md: calc(var(--radius) - 2px);
  --radius-lg: var(--radius);
  --radius-xl: calc(var(--radius) + 4px);   /* 16px — the default */
  --shadow-coffee: 0 2px 8px rgba(62,44,28,0.078), 0 1px 3px rgba(62,44,28,0.059);
  --shadow-coffee-lg: 0 4px 16px rgba(62,44,28,0.102), 0 2px 6px rgba(62,44,28,0.078);

  --transition: 0.15s cubic-bezier(0.4, 0, 0.2, 1);
  --transition-card: 300ms cubic-bezier(0.4, 0, 0.2, 1);
}

.dark {
  --background: var(--espresso);
  --foreground: var(--cream);
  --card: #4a3429;
  --card-foreground: var(--cream);
  --popover: #4a3429;
  --popover-foreground: var(--cream);
  --muted: #5a453a;
  --muted-foreground: #b5a598;
  --border: rgba(248, 246, 242, 0.10);
  --input-background: #5a453a;
  /* primary / accent / ring / destructive / success unchanged */
}
```

## 8. Raw source captured

`/private/tmp/.../scratchpad/` this session held `figma_index.html`, `figma.css`
(116 KB compiled Tailwind v4 — the two `:root` blocks above are lifted verbatim),
`figma_comp.js` (2 MB compiled app — className strings in §6 are from it), and
`figma_index.json` (scene graph: a single `CODE_INSTANCE` "App"). Re-fetch the URL if
you need to diff against a newer version.
