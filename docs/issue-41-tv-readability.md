# Issue 41 — TV readability acceptance, pre-deployment

All screens are rendered using **synthetic offline fixtures** in a disposable
headless Chromium job at 1920×1080 and 960×540; no TV, credentials, bridge,
customer data or network services are involved. The CI artifact
"synthetic-monitor-layout" contains per-channel PNGs and side-by-side PR/
deployment comparisons, retained for seven days. The existing real-TV
captures stay private at gway-001 and are not copied into the repository.

- GitHub PR cards stay in one column. Titles are 32 CSS pixels; repo #, State,
  CI and Merge have separate text-and-symbol indicators. Long titles wrap,
  without hidden truncation. Explicit unknown/blocked states remain visible.
- Deployment cards use two columns only from 1200 CSS px onward, otherwise one.
  Repo names are 30 px (29 px narrow), full SHA is stored as title/ARIA/data and
  shown as a full string on the selected card; 12 visible hex digits plus an
  ellipsis save horizontal space. Date is separate; installation, health and
  retry are distinct chips. Original evidence and retry errors remain intact.
- Remote arrow navigation follows visual grid: left/right on a two-column row,
  up/down jump two; narrow uses one step up/down. Enter still requests retry
  **only** for a failed component through the existing authenticated backend.
  Selected focus and channel-local scrolling are retained, no document scroll.
- No change to OAuth, pairing, secrets, backend deploy, source inventory, Fleet
  telemetry, or TV services. Keep PR Draft until visual acceptance and an
  explicitly authorized later merge/deploy. The real-TV screenshots were
  inspected via the private archive noted on issue #41.
