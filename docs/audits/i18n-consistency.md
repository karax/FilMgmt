# Filament Command Center — i18n Consistency

Status: **COMPLETE — 2026-09-13**

## Architecture

The frontend uses i18next with react-i18next and static `pt-BR` and `en`
resources. Portuguese (Brazil) remains the product default. A validated locale
is stored under `fcc-language`; an unknown stored value falls back safely to
`pt-BR`. Missing-resource fallback remains English, while recursive key-parity
tests prevent the two supported dictionaries from drifting. The document
`lang` attribute initializes from and follows the selected language.

## Canonical terminology

| Concept | pt-BR | English | Notes |
|---|---|---|---|
| Inventory | Inventário | Inventory | Primary collection |
| Spool | Spool | Spool | Established product term in both languages |
| Print | Impressão | Print | User-visible job/workflow term |
| Print Tracker | Controle de impressões | Print Tracker | Module name |
| G-code | G-code | G-code | Technical term is not localized |
| Settings | Configurações | Settings | Application preferences |
| Manufacturer | Fabricante | Manufacturer | Catalog concept; entity names are unchanged |
| Material | Material | Material | Catalog concept; entity names are unchanged |
| Estimated weight | Peso estimado | Estimated weight | Display label only |
| Estimated time | Tempo estimado | Estimated time | Display label only |

Action labels use concise natural phrases instead of concatenated fragments.
Internal enum values such as `PLANNED`, `PRINTING`, `OPEN` and `ARCHIVED` remain
stable and map through bounded localized display labels.

## Findings and remediation

- Removed English leakage from the default-language shared shell, Inventory,
  Spool creation/edit/details and Print creation/edit surfaces.
- Localized form labels, helpers, placeholders, loading states, actions,
  destructive dialogs, status labels and user-visible accessible names.
- Preserved FUN-01 structured Print save-error handling and STO-01 structured
  G-code quota feedback while ensuring both use localized copy.
- Replaced display of arbitrary backend validation/detail text with known-code or
  safe localized messages at the audited Spool and Print boundaries.
- Aligned the Portuguese guide's references to controls whose labels changed.
- Kept language persistence and immediate switching; invalid saved values do not
  crash or become document language values.

## Formatting and data boundaries

Dates, decimal numbers, weights and percentages use the selected display
locale. Currency formatting combines that locale with the currency code stored
on the Spool/Print data; interface language never chooses or converts currency.
Different currencies continue to be totaled separately. Numeric input parsing
and persisted date formats were not changed.

Entity and user data are intentionally never translated: Spool display names,
manufacturer/material names, colors, stores, printers, notes, filenames, raw
G-code material labels and identifiers such as `FIL-0007` retain their source
values. Technical units and payload values also remain stable.

## Validation scope

The bilingual browser matrix covers Inventory, New Spool, Spool Details, Create
Print, Finish Print, QR Scanner, G-code and Settings. It also checks immediate
switching, reload persistence, the document language and horizontal overflow at
390×844 for Inventory, Create Print, G-code and Settings. Mocked representative
API data keeps this validation read-only and preserves entity strings.

## Deferred to later Wave 2 work

- **Wave 2.2 — Accessibility:** broad contrast, focus management, keyboard and
  assistive-technology remediation beyond translated accessible copy and `lang`.
- **Wave 2.3 — Catalog Onboarding:** manufacturer/material management and first
  use flows.
- **Wave 2.4 — Mobile UX:** layout redesign beyond the translation-length
  overflow spot check.
- **Wave 2.5 — Application States & Feedback:** broader state and feedback
  redesign beyond localizing existing states.
- **Wave 2.6 — Authentication:** low-priority defensive hardening for the current
  trusted single-user LAN/Tailnet deployment; raise priority only if the trust
  model changes.

No database schema, backend enum, persisted entity value or production data was
changed.
