# Custom Power BI visual compatibility — 0.12.0

Death2PowerBI can import self-contained `.pbiviz` packages and execute compatible visual bundles in isolated browser frames. It also discovers `*.pbiviz.json` resources embedded in PBIX/PBIP ZIP imports, including existing saved reports. Report visual types are matched to package GUIDs; embedded versions are preferred for their original report. Package versions are identified by resource-content hashes, so importing the same package twice does not replace other packages.

## Use

Refresh the application and open **Custom visuals**. Choose a `.pbiviz` file to install it locally. Select an installed visual and assign fields to its declared roles to preview it against the selected report's semantic model. A numeric column assigned to a Measure role uses Sum; existing model measures use their DAX definition. Preview mappings are temporary and do not edit report pages. For an imported report that already contains that visual GUID, its existing role bindings are used automatically.

The supplied Resizable Gantt, Animated Bar Race v5 and Topology Map 2.0.0 packages have been registered in this local installation. Package code is stored in `custom_visuals/`; source reports and converted data remain in `data/`. These private runtime folders are excluded from the distributable ZIP. Install a visual again when moving to another installation, or import the original report with its embedded visual resources.

## Implemented host contract

- Constructor/update/destroy lifecycle with viewport changes and rendering event callbacks; API **5.11.0** tested with the three supplied packages.
- Table, categorical, categorical values grouped by a series/time role, and single-value DataView adapters. Column roles, types, model number formats, dates, base visual formatting objects and table/category/series row identities are supplied. Duplicate categorical cells fail explicitly instead of choosing a value silently.
- `createSelectionIdBuilder` for tables, categories, series and measures; selection manager select/clear/multi-select; source selections are restored after page redraw. Report selections filter other visuals through the existing relationship/filter engine and respect NoFilter rules. A preview's selections do not change report filters.
- Filter-capable custom visuals, including WeightedDualLabelSlider, receive their saved/current `jsonFilters` and can call `applyJsonFilter` on a filter property declared in their package capabilities. Basic In/NotIn and numeric/equality/blank Advanced filters are translated into the shared structured filter engine, scoped to direct model columns bound to that visual. Merge/removal affects only the emitting custom control's filters, respects report interaction rules, and preserves the slider's full domain. Unchanged filter messages do not trigger another redraw. An unbound target, unsupported filter or oversized payload is rejected; raw SQL is never accepted from the sandbox.
- Palette, basic localization fallback, tooltip show/move/hide, render events, limited host capabilities and local base-object `persistProperties`. Persisted values are scoped to report, visual instance and exact package version in this browser. These are local overrides, not edits to the original PBIX. The full Power BI formatting pane is not implemented.
- CSP-restricted sandbox frames (`allow-scripts`, without `allow-same-origin`). Visual code cannot use the application's DOM, storage origin or API bridge. Parent messages are checked against the exact frame window and random instance token; selection indices are validated against the rows already provided. Persisted properties are limited to declared object/property names. Frames are disposed on page/report/view changes.

## Network behavior

Visual network access is **off by default**. Topology Map still draws imported/model geometry and elevation perspectives; remote raster tiles, labels, imagery or URL-loaded topology are unavailable in that mode. A note explains blocked resources.

The package's **Allow declared external resources** checkbox permits HTTPS image/data requests only to the valid domains declared by its WebAccess privilege. The UI lists these domains before enabling them. The change takes effect on the next render. Enabling this allows visual-authored requests to those services; requests can contain information selected by that visual's code. It does not enable remote JavaScript, application-origin access, authentication tokens, downloads, popups or top-level navigation. Browser CORS restrictions still apply. Localhost/IP-literal network privileges are not accepted. Only enable network access for packages/services you trust.

The sandbox restricts authority; it does not guarantee protection from a poorly implemented visual consuming excessive browser CPU or memory.

## Tested packages

| Package | Browser verification |
| --- | --- |
| ResizableGantt.pbiviz | Tasks, exact dates, milestones and percentage progress rendered. Selecting Design filtered the neighboring native table from country totals to France = 10, and the task remained selected after redraw. The field-role preview also rendered all four test tasks. The actual **Power BI Releases → Page 7** now renders its embedded Resizable Gantt; the current query preview is capped at 1,000 tasks and reports truncation. |
| AnimatedBarRace_v5.pbiviz | Category values were pivoted into time-grouped categorical value columns. The actual bundle rendered France/Germany, advanced from 2020 to 2021 and paused. This package does not call the selection manager to provide report cross-filtering. |
| TopologyMap.2.0.0.pbiviz | Rendered four model points, a semantic-model line, zoom controls and elevation perspective while external tile requests were blocked. External-service rendering was not enabled during validation. |

The disposable verification report was removed after testing; the user's saved reports were preserved. All three packages' original JavaScript bundles were used, not replacement charts.

## Remaining compatibility limits

This is a Power BI visual-host compatibility layer, not the Microsoft host. A package importing successfully does not guarantee it can render. Unsupported services raise a clear error or warning.

Matrix/tree DataViews and matrix identities, drill-through/bookmarks, full formatting/analytics panes, tuple/relative-date/text-search custom filters, custom sort, highlight data views, per-data-point property persistence, storage APIs, external script dependencies, licensed-service integration, Entra authentication, modal dialogs, download/export services, remote assets outside declared HTTPS services, and fetch-more-data paging are not implemented. Table/categorical previews currently retain the application's 10,000-row query limit. Some packages require richer metadata/schema features than the current adapters expose. Use a self-contained bundle that registers its GUID in `window.powerbi.visuals.plugins`.

## Validation and sources

Run `py test_custom_visuals.py` for archive/metadata validation, or pass package paths to validate the three files. Run `node test_custom_dataview.js` for table/date/format adaptation, grouped time-series values, identities, duplicate-cell rejection, CSP construction and script-closing-tag escaping. Run `node test_custom_filter_visuals.js` for saved slider selection, domain retention, filter compilation, sandbox feedback, bound-column validation, duplicate suppression and isolated removal. Existing query, DAX, numeric format, chart and interaction tests also remain applicable.

Implementation references: [custom visual packages](https://learn.microsoft.com/en-us/power-bi/developer/visuals/develop-power-bi-visuals), [visual lifecycle and host APIs](https://learn.microsoft.com/en-us/power-bi/developer/visuals/visual-api), [DataView mappings](https://learn.microsoft.com/en-us/power-bi/developer/visuals/dataview-mappings), [selection API](https://learn.microsoft.com/en-us/power-bi/developer/visuals/selection-api), and [privilege status API](https://learn.microsoft.com/en-us/power-bi/developer/visuals/permissions-api).


## Accounts (0.13.0)

Sign-in is required. Package imports and embedded visual packages are granted to their uploader/report owner; other normal accounts cannot list or retrieve that package code without their own grant. Admin can access all packages. Identical packages remain deduplicated while grants are separate. Base-format and network settings are now scoped to the signed-in account, and package caches/frames are cleared on sign-out or account change.

### Violin Plot (1.3.0) and legacy bundles

The original Violin Plot (1.3.0), package version 1.3.0.4 / API 2.5.0, is supported through the custom-visual sandbox. PBIX imports preserve its GUID and original sampling/measure roles instead of substituting a Vega-Lite plot. Embedded packages are registered automatically, including during existing-report metadata upgrades. Legacy `externalJS` entries containing safe relative build paths are treated as metadata only; the supplied `content.js` must already contain its dependencies. No dependency paths are read or downloaded; remote/unsafe script paths are rejected. Legacy color-palette arrays and common visual API enums are supplied by the shared host. Small custom frames use their actual viewport size. Static snapshot exports use the same rendered-frame capture path as other custom visuals.

For Violin package 1.3.0.4 only, the sandbox applies a guard for an upstream missing-axis-generator dereference in the no-category, hidden-axis layout. Its distribution calculation and source formatting remain in the original bundle. Other package versions are not patched.

Deneb visuals run in the existing opaque-origin iframe sandbox. Vega expression compilation is enabled only for Deneb packages; network access remains disabled by default. An exact compatibility repair handles the damaged ellipsis regular expression found in embedded Deneb 2.0.0.0 bundles.
