# Death2BI

A local Power BI migration workbench with account-based access, private report libraries, and an administrator account.

## Embedded map coordinates for arbitrary location fields (0.24.33)

Bubble and point maps can infer latitude and longitude from the model table containing their bound location field, regardless of whether that field is named City, LGA, an administrative code or a localized name. Inference requires a unique same-table coordinate pair with numeric types when type metadata is present. Authored coordinate bindings take precedence; ambiguous, incomplete or nonnumeric inferred pairs are left alone. Country and polygon maps retain their existing geography behavior.

Locations containing multiple model rows use the unweighted mean of valid embedded coordinate pairs. Separate aggregation contexts preserve the original bubble-size measure and its filters rather than weighting the coordinates by duplicated fact rows. Invalid pairs are excluded together; row-level security applies to both coordinates and measures. Existing imported reports benefit without reimporting. Verified all 17 locations and 2,000 visits on Website Analytics Dashboard's Website Visits page.

## Administration sharing links (0.24.32)

Administration includes a Sharing links section alongside Public report links. Administrators can inspect single-use invitations across all report owners, including the report, link ID, creator, creation time, used/unused/expired status, recipient, expiry and removal history, and remove links. Recipients must sign in to accept these invitations. Removing an unused invitation prevents redemption; removing a used invitation retains its audit record and does not revoke access already granted to its recipient. Revoke that access through Share report. Link secrets remain visible only when originally generated. The same sharing-link list remains available under Accounts.

## Shared calculation and custom visual fixes (0.24.31)

Eligible physical-table SUMMARIZE calculations batch safe aggregate dependencies and reuse their exact group context rather than repeating the same scans. Grouping-only SUMMARIZE avoids unused context transitions. DuckDB schema metadata and relationship paths are reused within one evaluation; security, cancellation and calculation budgets remain in effect. Complex expressions continue through the original evaluator when the optimization cannot preserve their semantics. The Employee Details utilization line in LearnPowerBI and the Financial Metric Navigator in Metric Map now complete within the existing time budget, without changes to their source DAX.

Custom visuals retain scalar measure projections that Power BI marked inactive for drill state, and mixed grouping/measure roles receive correctly typed categorical and numeric channels. Dynamic native Series/Legend columns retain source theme colors independently of stale category-only color selectors. Explicit series color overrides, authored legend visibility, and valid series-based conditional formatting are preserved.

Walkers (wishyoulizationwalkers) is available as a pinned, hash-verified offline package. PBIX/PBIP imports attach it automatically when referenced and not embedded; loading an existing saved report also attaches the known package. Embedded author-supplied packages take precedence. Unknown custom visuals are not downloaded automatically. Package access still requires report authorization, and sandbox restrictions remain in place. Its MIT license and source provenance are included in bundled_visuals. The legacy package's numeric formatter supports its default rounding/percentage expression and a bounded set of numeric formats without dynamic JavaScript evaluation; unsupported arbitrary formatter expressions fall back to the unformatted value.

These changes apply through the shared conversion, calculation and rendering paths to existing reports and future imports. Installed reports, source data, sharing permissions and personal settings are retained.

## Full screen report canvas (0.24.30)

Full screen beside the saved-report controls displays only the current report canvas, centered and scaled to fit while retaining its aspect ratio. Press Esc to exit. Authored visual controls, slicers, bookmarks and interactions stay available; application navigation, chart-conversion menus and export/filter-inspection controls are hidden. Filtering and report-page navigation preserve the fullscreen host while the canvas updates. Report-page tooltips and slicer popups remain visible inside fullscreen. HTML reports use their viewer as the fullscreen target.

Native browser fullscreen is preferred. If it is unavailable in an embedded browser, canvas-only presentation fills the browser viewport with the same Esc behavior. Leaving the report restores the usual layout. No reimport is needed.

## Download original reports (0.24.29)

Download report beside the saved-report controls retrieves the retained PBIX, PBIP project ZIP, or stored HTML report. The filename matches the report header/original upload name, including Unicode names. Legacy names without an extension receive the retained source type's extension. The browser downloads the file directly from a streaming endpoint; large files do not require a full-size Python buffer or JavaScript Blob.

The existing source-export permissions also apply: sign-in and report access are required; public links cannot download original files, and row-level security or hidden-page restrictions prevent raw-source downloads where applicable. Missing originals produce an explanatory message. Existing HTML imports retain normalized UTF-8 source, so their download reproduces the stored report rather than restoring an original BOM or legacy encoding. PBIX and project ZIP downloads preserve their retained original bytes. No reimport is needed.

## Responsive visual loading and cancellation (0.24.28)

Report visuals load through a bounded queue of three tasks, yielding browser time before planning, querying, chart embedding and alternate-view capability checks. Navigating to a page, report or another tool, changing filters or selections, and leaving a tooltip cancel obsolete work immediately. Requests retain the signal of the view that created them; stale responses cannot update a newer view. Vega mounts and small multiples release obsolete views, handlers and observers, including embeds that complete after cancellation.

The query cache preserves completed results and shares pending work only while there are live consumers. Its final consumer leaving aborts the transport. Owner-scoped cancellation reaches queued/running DAX process jobs and interrupts SQL/DuckDB work, including secured-connection setup. Anonymous report links can cancel only their own requests. Existing query/RLS time budgets and access checks remain in place.

Alternate chart menus test a representative sample of at most 64 rows instead of building dozens of complete alternate charts. The displayed chart and its query still use the complete visual result. Cooperative scheduling keeps input and navigation available between tasks; an individual synchronous browser layout or Vega compilation step still runs until its next boundary. The changes apply to existing reports and future imports, and do not require reimporting.

## Report-page tooltip filter context (0.24.27)

Report-page tooltips retain the hovered point identity, physical source filters, and the target page's own filters. Source visual measure-result filters are applied at the source grain and are no longer reapplied as column filters inside tooltip queries at a different grain. Mixed Boolean conditions retain only logically safe physical restrictions; source Top N predicates are removed only when the hover identity proves the ranked field selection. Target tooltip measure filters, report/page filters and security enforcement remain in place.

This restores the tooltip headers and charts in Family Missfortunes.pbix and applies to existing reports and future imports without reimporting. If every tooltip visual fails, the popup shows a diagnostic instead of a silent blank page.

## Initial group visibility and map legend settings (0.24.26)

The converter recognizes hidden flags inside legacy `singleVisualGroup` and normalized `visualGroup` definitions, propagating group visibility to descendants while retaining each child's own visibility. Explicit modern root flags remain authoritative. Hidden visuals remain available to authored bookmarks and retain their filters and data bindings; they are omitted from the initial rendered page. Parser version 36 refreshes saved metadata automatically without replacing report data or access permissions.

Disabled legends stay disabled across chart layers and map rebuilds. Location and bubble-size fields alone do not create automatic map color legends. Source legend fields and explicit legend settings retain their requested legends; automatic bubble-size legends remain off. Verified initial visibility and bookmark switching on Data Stories and Tactics & Targets in Global Terrorism Database Analysis.pbix. The shared fixes apply to existing reports and future imports without reimporting.

## Plot artwork boundaries and bookmark action scope (0.24.25)

Chart plot-area images are clipped to the plot bounds. Normal-fit artwork retains its original size and alignment while no longer covering category labels, axis titles or legends outside the plot. Existing fit modes, chart marks and conditional colors are retained. This corrects the hidden country names beside the bar chart in Halloween Contest 2026 - Pavan_Kalyan.pbix.

Bookmark actions apply to selected visuals only when the source explicitly enables `applyOnlyToTargetVisuals`. Omitted or false flags apply the full saved state even if a stale target-name list is present. Saved data/display options, scoped bookmarks, group visibility and omitted visual snapshots retain their existing behavior. This restores the image-driven game sequence in Halloween Contest 2026 - Adrian Liu 29.pbix. Both shared fixes apply to existing saved reports and future imports without reimporting or changing source files.

## Conditional chart range colors and category gradients (0.24.24)

Conditional colors support Power BI's RangePercent thresholds and scoped summaries over AllRolesRef. Bounds are calculated from the complete executed visual result after filters and Top N, using exact projected field identities, and are recalculated after interactions. Already plotted measures require no extra query. A separate formatting-only measure is loaded once per category in a grouped request before its bounds are calculated locally. Unsupported scopes or incomplete domains produce a formatting warning and retain fallback paint instead of inventing a threshold.

Category-role color selectors now apply to real categories, including blank categories. This preserves two- and three-color gradients for donut/pie slices, bar and column marks, their enabled data labels, and category legend swatches. Static and field-value overrides retain their existing behavior. These changes apply to existing reports and future imports without reimporting. Verified the original rules in Halloween Contest 2026 - Pavan_Kalyan.pbix against independent response counts, including filtered-domain recalculation.

## Reliable button slicer hit areas and rapid selections (0.24.23)

Button slicers fill the available space within their authored visual bounds even when values, fills and outlines are hidden. Transparent controls used over an HTML or image panel retain their full button hit areas and accessible value labels. Display text stays hidden when disabled in the source. Visible, image and vertical button layouts retain their selection formatting and original visual bounds.

Categorical slicers update their local selection and button feedback before requesting an asynchronous page rerender. Rapid Ctrl/Cmd clicks, repeated toggles and clearing therefore use the latest selection rather than the selection captured when the old control was mounted. Saved filters are copied, and authored single/strict-select and modifier-key settings remain authoritative. These shared fixes apply to existing reports and future imports without reimporting.

## Navigator orientation (0.24.22)

Page and bookmark navigators honor the source Grid layout Orientation setting. Vertical buttons stack within the navigator's original bounds, retaining their authored spacing, labels, order, page visibility, bookmark group and navigation targets. Horizontal and omitted orientations retain horizontal layout. The shared renderer applies this to existing saved reports and future imports without reimporting or modifying report data.

Verified all three vertical page navigators in Marketing Analytics - Interactive Dashboard.pbix and their page navigation actions. Regression checks cover both navigator types, direction changes on rerender, inherited layout settings, spacing and hidden-page/bookmark filtering.

## Legacy hidden visuals and synced slicers (0.24.21)

The converter recognizes legacy `singleVisual.display.mode: hidden` in addition to modern PBIR `isHidden`. Explicit modern boolean flags retain priority; omitted modern flags fall back to legacy visibility. The resulting initial visibility propagates through parent groups and remains separate from bookmark snapshots, so authored bookmarks can reveal a hidden pane without revealing unrelated hidden copies on other pages.

Hidden slicers remain in the semantic report definitions. Their active filters, synchronization groups, query fields and bookmark state are retained while their controls are omitted from the page. Verified Marketing Analytics - Interactive Dashboard.pbix: all four hidden slicers on both Customer Segmentation and Campaign & Channel Analysis, the hidden customer-tooltip slicer, Age >= 20 filtering, and scoped Overview pane bookmarks. Parser version 35 automatically refreshes saved report metadata when opened; no source PBIX, DuckDB data, Parquet files, permissions or account settings are replaced.

## Decorative textboxes and report header visibility (0.24.20)

Empty textboxes with a visible authored background, border, or shadow are preserved. Reports commonly use these as background panels beneath other text, separator lines, and footer bands. Omitting an empty dark panel could otherwise make white overlaid text disappear against the page canvas.

The shared renderer checks both resolved paint settings and their source: theme defaults, padding or radius alone do not create blank elements, and disabled or fully transparent decoration stays omitted. Existing layering, dimensions, typography and caption enable/disable settings remain intact. Verified the original PBIR definitions in New Fears - Familiar Shadows.pbix, including its charcoal header panel, three white header textboxes, both dividers, and footer panel. Existing saved reports and future conversions receive the fix without reimporting or source changes.

## Dynamic SVG image verification

Measure-driven SVG images use the same shared image path as static image URLs. Raw or partially escaped SVG markup is normalized without losing percent signs, color hashes, embedded font URLs, Unicode, apostrophes, animations or viewBox coordinates. Dynamic query results retain the visual's original fit, transparency, background, border, layer and alternative-text settings. Blank results omit the image; unexpected query errors remain errors rather than substituting unrelated data.

The three reported dynamic images in Mystery Inc.pbix render successfully in the current build. The saved Case 3 outputs were checked against original measures, embedded fonts and independent physical-data counts, and all three outputs were verified for six additional case selections. Portable regression coverage exercises SVG URLs and the production SQL/Python image-query flow; no report-specific source or rendering rewrite was needed. Reload an older open application tab to use the current renderer.

## Visual number formats and stacked-area series fidelity (0.24.19)

Legacy report `columnProperties[queryRef].formatString` overrides are retained when compiling visual queries and formatting values. These visual-specific VBA formats take priority over the semantic column format; authored element overrides and modern projection formats retain their existing priority. Exact field references prevent one visual's format from affecting another visual using the same model field. Cards, chart labels, axes, tables and tooltips share this resolution, including explicit zero decimal places.

Static data-point color selectors are distinguished from row-dependent color expressions. Connected area charts preserve separate series even when two series share the same color, and their fill and outline use the same stack geometry. This corrects merged series and zigzag gaps without changing data, colors or relationships.

Verified Logistics Operations BI analysis.pbix against the original visual definitions and independent SQL totals. Both affected expanded date axes retain all 36 Year/Month positions in chronological order (January 2022–December 2024), and new real-Vega regressions cover both Category-first and value-first query layouts, compound hover/filter identity and monthly sorting. Existing saved reports receive these shared improvements without reimporting.

## Exclusive sentence and report-page tooltips (0.24.18)

When a sentence or report-page tooltip is active, the shared renderer disables both the standard Vega popup and the browser-native data tooltip. Vega needs an explicit empty tooltip handler: passing `tooltip:false` to VegaEmbed alone leaves Vega's built-in browser-title handler in place. Standard tooltips remain available when neither replacement is configured, and source tooltip disable settings continue to suppress all data tooltips.

Cards, tables, matrices, and sandboxed custom/HTML visuals also suppress their native data titles while a replacement tooltip owns presentation. Cached table sorting and conditional-formatting repaints retain that policy. Visible chart titles, subtitles, accessibility labels, and control help are preserved. These changes apply to existing saved reports and future conversions without reimporting.

## Enabled sentence-template tooltips (0.24.17)

Sentence templates render only when the source's Sentence format setting is enabled and tooltips are enabled. Disabled or omitted Sentence format retains standard or report-page tooltip behavior; disabled tooltips suppress native Vega popups as well. An active report-page tooltip retains priority over a sentence template.

The shared renderer substitutes available fields from the hovered query row, preserving model/visual/dynamic number formats, original and renamed field aliases, line breaks, bold values and authored text/value/background colors. Unknown or ambiguous placeholders remain literal, consistent with [Microsoft's sentence-tooltip documentation](https://learn.microsoft.com/en-us/power-bi/create-reports/desktop-custom-tooltips). Template text and values are escaped. Hovering uses cached results and performs no extra DAX queries.

Verified both charts and all five colleges in Sentence Tooltip Exercise.pbix, including the renamed Enrollment Arrow field, positive and negative year-over-year percentages, multi-line sentences, and bold substitutions. Shared tooltip hooks apply to existing saved reports and future conversions without reimporting or modifying source templates, measures or data. Original row context and dynamic formats survive chart scrolling, sampling, facets and highlights.

## Inline IDFX storage and recovery of incomplete imports (0.24.16)

The embedded-model decoder supports IDFX streams that store column data followed by CP metadata and a metadata-length footer. The adapter validates stream boundaries, segment counts and serialized row counts before passing the original payload to PBIXRay. Ordinary companion-metadata storage uses the existing decoder. No rows or calculated-table values are inferred, and no external data source is refreshed.

Saved imports with unavailable tables automatically retry extraction once per storage-decoder version when opened and idle. Repairs stage and verify the database and Parquet files before publication, retain existing converted tables, report IDs, workspaces and sharing, and rebuild relationships, formats, sorting and data-dependent presentation metadata. Failed publication rolls back the database and new Parquet files. A new revision invalidates stale query results.

Verified Halloween Poster.pbix: all seven tables and five relationships were recovered from the original source snapshot. The line chart and five bar charts execute successfully; results match independent physical-data calculations. The Period table remains a disconnected two-row selector table, as authored. Source DAX and PBIX bytes are unchanged. If a table still cannot be extracted, visual queries and SQL report its extraction diagnostic rather than a misleading database catalog error.

## Image interaction states and compact cards (0.24.15)

Image visuals resolve Default, Hover and Pressed independently from the shared All settings. Each state preserves its image source, transparency and fit. Pointer and keyboard interactions return to the appropriate state on release, leaving the visual, cancellation or loss of focus, while retaining existing navigation actions. Existing saved reports and future imports use the same renderer; original image resources are unchanged.

Compact New Card visuals preserve their authored layout padding independently of visual-container padding, so short cards used as overlaid chart labels do not acquire unnecessary scrollbars or clip their values. Scrollable horizontal bar charts also reserve sufficient scroll range to reach the final category, including short visuals, multiple series and resized charts.

Verified Halloween_Contest_26_Sergio_Lazaro_BI_Nightmares.pbix: both Top 3 queries return three nonblank fears; the shared card-layout fix keeps their separate overlaid labels within their authored bounds. The image's Default state is fully transparent, Hover displays its alternate eyes image, and Pressed displays the blood image. Source DAX, data, report permissions and settings are retained.

## Authored image transparency and fit (0.24.14)

Image visuals preserve their authored image transparency, independently of container backgrounds, borders, titles and layer order. Source percentages, including zero and full transparency, resolve through the existing theme and visual-property precedence. Opacity is retained by snapshot export, and original image bytes and embedded alpha are preserved.

Image fit modes preserve their authored meaning: Fill crops proportionally, Fit contains the whole image, Stretch fills the bounds with independent scaling, and Center/legacy Normal uses native sizing with centered clipping. Navigation icons retain their contain behavior. See [Microsoft's image visual documentation](https://learn.microsoft.com/en-us/power-bi/visuals/power-bi-visualization-image-visual).

Verified image `54a90d438525a20485bb` in Halloween_Contest.pbix: its authored 85% transparency renders with 0.15 image opacity, revealing the card and text behind it. Its Fill setting uses a centered crop rather than stretching; the existing label at the top of the embedded PNG falls outside that crop. The embedded PNG is byte-identical to the PBIX resource. Shared renderer tests cover defaults, literals, theme overrides, fit geometry, container isolation and snapshot retention. This applies to existing saved reports and future conversions on reload.

## Virtual iterator columns and HTML Content measures (0.24.13)

The running-total SQL optimization checks physical lineage and its supported calculation shape before resolving model-column metadata. Temporary columns such as `[Value]` from `GENERATESERIES`, table constructors and `SELECTCOLUMNS` aliases retain their iterator row context and use the bounded evaluator when the SQL optimization does not apply. This also prevents accidental binding to a same-named physical column in a measure's home table. Eligible physical running totals retain their existing fast path, and actual missing model columns still produce errors.

Verified all four affected HTML Content visuals in Halloween_Shafi_Ullah.pbix: generated SVG digits, glyph offsets, widths, percentages and retained-fear indicators match independent queries against the physical data. All 16 data-driven visuals pass; 53 targeted regressions cover virtual rows, physical optimizations, context transitions and SQL safety. The fix applies to existing reports and future imports without changing source DAX, report data or evaluation budgets.

## Map fitting, chart hierarchies and matrix gradients (0.24.12)

Point and filled maps fit their actual geographic extent, including regional and city-sized coordinate clusters. Automatic fitting and all navigation controls share finite zoom bounds of 1–65,536 times the world projection. A single or coincident location retains a bounded regional default. Invalid coordinates and empty data receive finite defaults.

Bubble maps use Size for bubble area without automatically generating a size legend. Authored category legends retain their field labels, visibility, placement and stable category colors. Uniform per-category visual color overrides use the same scale for map bubbles and legend swatches.

Initial fitting, Fit to data and automatic resizing use Vega's completed projection layout, accounting for legends and padding. Manual navigation remains preserved when resizing or revisiting the same location set; a changed location set fits again. Map controls are released safely if the page changes during asynchronous layout.

Verified all 176 LFRS incident locations inside the padded projection viewport. The shared fix applies to existing reports and future imports. Checks cover real Vega scenes, narrow extents, visible legends, singleton/empty data, all zoom inputs, resize/cache behavior, point selection and asynchronous cleanup.

Chart hierarchies retain the source's active axis levels even when no expansion-state metadata is present. Expanded numeric levels such as Year / M use a compound categorical axis and identity, with scroll width based on the complete category key. Descendant category sorting stays within parent groups; invisible ordering prefixes remain significant. Single-level numeric and date axes retain their continuous scales. LFRS's 41 Year / M categories were checked against the actual query results and Vega rendering.

Table and matrix color gradients bind to each cell's exact field or aggregation. Automatic ranges include all matching pivot cells for the same value projection, with the authored totals/subtotals and blank handling applied. Missing pivot tuples retain blank sibling inputs. Domains, prepared gradient scales and cell contexts are cached for the current result and local sorting; a new filtered render rebuilds them. A 10,000-row check verifies one preparation and no repeated domain scans during sorting. Both LFRS heatmaps were checked across 168 cells each using the authored Count of random id gradient: 70 → yellow (`#FFD900`), 204 → red (`#AD1914`), 338 → dark red (`#4B0000`), with no color mismatches.

## Transparent card tooltip targets (0.24.11)

Cards used as transparent report-page tooltip targets retain their authored hover area when both the value and category label are hidden. Hovering the background or padding of a single scalar card also resolves its tooltip. Grouped and multi-card visuals keep their per-card row identity; interactive controls and disabled tooltips retain their behavior. This applies to existing saved reports and future imports without changing the authored visibility settings, bounds, source DAX or data.

Verified the card linked to “Infobulle peurs gardées” in The Monster Under the Bed Didn't Leave. It Moved..pbix. Checks include hidden card content, scalar background/padding hover, multiple/grouped card identity and disabled tooltip behavior.

## Nested DAX safety and visual-series formatting (0.24.10)

Before lowering a grouped iterator to native SQL, the compiler checks its expression and measure dependencies for nested grouping, aggregate contexts spanning multiple relationship hops, and relationship overrides. These shapes use the bounded evaluator instead of generating a fragile correlated SQL plan. Ordinary eligible one-hop summaries keep the SQL fast path. The same secured connection, source DAX, filter context and original time/step limits apply. Evaluation diagnostics identify SQL safety fallbacks and their reasons.

Chart formatting expressions that summarize already-rendered series, such as an average reference line over a measure, are evaluated from that result set. They are not sent to the model-column aggregate endpoint. Bar, column and line charts can display these authored reference lines. Unsupported direct model aggregate requests receive a descriptive validation error instead of a Python `KeyError`.

Regression coverage includes nested summaries, multi-hop context transitions, safe one-hop plans, secured views, budget handling, and local series formatting. LearnPowerBI's Executive Summary, Division Management and Branch Management are checked using their actual saved filters, concurrent reused workers and a physical-hours arithmetic cross-check. These fixes apply to existing reports on reload and future conversions without reimporting or changing authored measures.

## Adaptive categorical x-axis labels (0.24.9)

Shared charts prefer horizontal category labels when neighbouring labels fit without overlap. The renderer measures labels using the resolved font, available category spacing and scrollable chart width. Where needed, text can wrap at spaces into two lines before diagonal or vertical placement is selected. Explicit source/theme angles, hidden axes and numeric/time scales retain their settings.

Label angle, alignment, baseline and rotated text limits respond to chart resizing. Rotated labels have a bounded extent so short visuals retain plotting space. Small multiples use each chart cell's width. These changes apply to existing reports on reload and future report conversions, without changing source data or DAX.

Verified the two category labels in The-Midnight-Shift-2026-FINAL-GPV2.pbix. Checks: `node test_x_axis_labels.js`, plus shared chart, scrolling, formatting, combination-chart and tooltip regressions. The new regression renders actual Vega scenes and exercises width/height resizing, word wrapping and preserved axis settings.

## Palette neutrals and embedded AVIF artwork (0.24.8)

Power BI palette entries 0 and 1 resolve to white and black independently of named structural colors such as `foreground` and `background`. Dark report themes no longer turn an explicitly black palette background white, and palette tint/shade values continue to apply. Named structural colors and data-series palette entries retain their own values.

Embedded AVIF images are preserved with their original bytes, MIME type and transparency. This applies to new PBIX/project imports, automatic metadata upgrades for saved reports, image rendering, embedded SVG raster images and snapshot export. Image visuals retain their disabled container backgrounds and borders through the shared theme resolver. Existing asset size limits and SVG restrictions remain unchanged.

Verified against Wärmestreifen.pbix. Existing reports receive the shared rendering fix on reload; metadata upgrades restore previously skipped AVIF resources without replacing semantic data or authored DAX. Checks cover palette and named colors, disabled/enabled image backgrounds, asset alpha-byte preservation, image budgets, SVG safety and snapshot image retention.

## Shared grouped aggregates and worker diagnostics (0.24.7)

Grouped scalar DAX queries can reuse identical eligible numeric aggregate subqueries within the same secured filter context. Measures with repeated category totals, ratios and text classifications retain their source expressions while producing a smaller DuckDB query plan. Iterator-local and outer-variable-dependent aggregates are excluded from sharing. No cache is shared between requests or users, and execution limits are unchanged.

Eligible `ADDCOLUMNS` context transitions use batches of at most 64 group identities per SQL plan, including inner iterator calls. Batches preserve input order and lineage and share the original request budget and secured connection. This bounds native query-plan complexity without truncating the iterator's data.

DAX worker failures now distinguish native process exit codes from ordinary DAX exceptions. A bounded private stderr tail is drained to avoid blocked worker pipes and is logged server-side when a worker fails. Client errors and administration status expose only sanitized exit codes and reasons. A failed worker is replaced; its diagnostic text is not returned as report data.

Verified the Customer Cross-Sell Map in Week 35 2026 .pbix, including its two HTML visuals and the 731-row customer action matrix. Source data, DAX and saved report settings are unchanged.

Checks: `py -m unittest test_shared_group_aggregates test_add_columns_batches test_dax_pool test_dax_pool_http` plus affected DAX regressions. The matrix's eight fields and 731 rows match the previous calculation; execution fell from about 34 seconds to 2 seconds on the test machine.

## Bar chart axis bounds (0.24.6)

When a bar or column chart specifies only its maximum, its automatic minimum retains the zero baseline. Previously, an upper bound could disable zero inclusion and make the smallest nonzero value appear to have no bar. Explicit minimums, negative maximums, logarithmic scales and non-bar axes remain separate. This shared behavior also covers stacked/normalized columns and the bar portion of combination charts.

Bar transparency now resolves category, metric and field-valued overrides through the shared property resolver. Transparent bars can still have visible labels and overlaid artwork. Verified the Responses Where Fears Remained chart in WeNeverStopFearing.pbix: Heights is 4 and displays proportionally on the authored 0–7.5 scale. Source data and measures are unchanged; existing reports receive the fix on reload, and future imports use the same renderer.

Checks: `node test_bar_axis_baseline.js`, `node test_bar_transparency.js`.

## Per-series bar and column labels (0.24.5)

Bar and column visuals preserve per-series data-label visibility and measure-driven label values. An invisible helper series can carry descriptive labels while its bars remain transparent; another series can keep its numeric labels disabled. Scoped font, color and number-format properties remain associated with their own series, and disabled global labels remain hidden. The shared renderer applies these behaviors to existing models and future imports.

Verified all three charts in What is our fear.pbix, including the Top N tie in childhood fears. The earlier shared Top N/optional-formatting query corrections cover this report's loading path; no changes to the authored DAX or semantic model are necessary.

## Selected-row calculations, scatter axes and image slicers (0.24.4)

Grouped DAX calculations can now batch eligible scalar parameter branches and fact-table cohort filters, accelerating Top N across large relationship-backed category domains. Polar scatter calculations support deterministic trigonometric expressions, typed date extraction and lazy constant branches. Eligible partial-row ranking scores use the shared grouped aggregate engine. Unsupported context combinations retain the bounded evaluator; source DAX and execution limits are unchanged.

Nested `ALLSELECTED(Table)` measures are supported while `FILTER` visits a proven complete physical selected-table domain. The evaluator retains that secured selected domain separately from each row's context transition, so selected medians do not collapse to the current row. Unproven nested iterators and relationship overrides remain unsupported.

The shared visual engine now translates static date-span filters, retains the executed Top N filter context for optional formatting, recovers stale default sorts only when a missing column uniquely matches a projected measure, enumerates category combinations through bidirectional bridges without using duplicated anchor aggregates, and renders source text columns on categorical scatter X axes. Numeric scatter sampling retains its existing validation and 3,500-point bound. Native button slicers can display image URLs with source layout, selection styles and report-page hover tooltips.

These changes apply to existing reports when opened and to future imports without reimporting reports. Verified against the scatter, donut, genre bars and poster button slicers in What Truly Makes a Movie Successful - World Champ BCN 2026 Round 3 Submission.pbix.

## Relationship aggregate performance and secondary chart axes (0.24.3)

Eligible aggregate measures grouped through relationships are calculated with a shared scan of the secured, filtered fact rows. Relationship bridge fan-out is removed per physical fact row and group, preserving duplicate fact rows, category identities and Top N ties. This accelerates large Top N category domains as well as grouped numeric aggregates. Unsupported expressions retain the bounded evaluator. Source measures and existing execution limits are unchanged.

Visuals combining Top N and measure filters now remove post-aggregation predicates before categorical filter resolution. Their filter measures remain hidden evaluation fields and are applied after the ranked result is calculated. Expensive display expressions, including SVG ratings, are evaluated for the narrowed result instead of failing in the direct-column filter parser.

Line and area charts with primary and secondary values now use independent left and right Y scales. The renderer recognizes modern `y2Axis` settings and legacy secondary-axis properties, retaining separate numeric formats, units, bounds, visibility, titles and colors. Data labels, trends and cross-highlights remain associated with the correct scale. Single-axis charts retain their existing behavior.

Verified on Who's Watching.pbix: The Mogul production-company bar chart and revenue/margin area chart, The Fan keyword bar chart, and the Climax table including its SVG ratings. These shared changes apply to existing reports when loaded and to future imports; no reimport is necessary.

Checks: `py -m unittest test_grouped_relationship_scans`, `node test_topn_measure_filters.js`, `node test_secondary_axes.js`.

## Matrix report-page tooltips and sparkline chart types (0.24.2)

Matrix rows and pivoted value cells now display assigned report-page tooltips. Hovering or focusing a row passes its row hierarchy and, for a pivoted value, its column hierarchy to the shared tooltip engine. Sorting and expansion keep these identities aligned with the displayed cells. Ordinary table rows use the same hover support. Disabled tooltips remain disabled and tooltip visuals do not recursively open tooltips. Charts inside tooltip pages fit their authored bounds without category scroll expansion or bar windowing, preventing them from overlapping adjacent tooltip visuals. Tables still expand to reveal their tooltip rows.

Hidden legacy tooltip pages are recognized from enabled Canvas page assignments when the PBIX does not provide a named Tooltip page type. They remain outside ordinary page navigation and unrelated hidden pages remain restricted. Existing reports gain the behavior when loaded; future imports use the same classification.

Matrix sparklines honor each field's **Chart type** setting, supporting Line and Column with source/theme colors. Column sparklines use a zero baseline, support negative values, and retain gaps for missing points. Verified the Optimized KPI Overview in Workout_Wednesdays_PowerBI_2026-w28.pbix: Column sparklines and the Details tooltip filtered to the selected KPI, returning 45 daily values. No report reimport is required.

Checks: `node test_matrix_tooltips.js`, `node test_matrix_sparklines.js`, `py -m unittest test_tooltip_pages`.

## Faster ranking measures and custom filter controls (0.24.1)

The shared DAX evaluator now compiles eligible row-local scalar expressions once per calculation and scores secured iterator rows in batches. `FILTER`, `ADDCOLUMNS`, `TOPN`, `RANKX` and repeated row-level measure references can reuse these results. This especially speeds up HTML Content ranking reports that score thousands of rows before showing a short list. Measures, page filters and model data are unchanged; unsupported context-sensitive expressions retain the bounded interpreter. Caches remain request-local and use the current secured connection. Existing 60-second/5-million-step limits remain in place.

The fast path preserves measure context transition, disconnected parameter selections, BLANK/zero distinctions, ties, text identity, lazy branches and row lineage. Floating-point filter identities now retain their DOUBLE type, preventing valid rows from disappearing when an iterator turns fetched values back into SQL predicates. Decimal values remain numeric. These changes apply to existing models and future imports without reimporting a report.

The custom-visual sandbox now implements capability-declared `applyJsonFilter` and supplies `jsonFilters` on updates. This restores interactive **WeightedDualLabelSlider** visuals using their original embedded package, source formatting and saved positions. Supported Basic and Advanced filters are validated against directly bound model columns before entering the shared page-filter engine. Undeclared properties, unrelated targets and arbitrary SQL are rejected. Custom filter controls honor page interaction settings, appear in the filter inspector, and do not offer Export data controls. Generalized support applies to other custom visuals using these supported filtering APIs.

Verified all six HTML Content visuals on the Ibrahim Abuelrish report's Verdict Page and Success Ranking Engine. Live server calculations completed in approximately 0.1–4.4 seconds, with the three ranking tables taking roughly 1.0–1.7 seconds. The report's three original sliders render with saved positions and changing a slider updates page filters. No timeout increase or source measure rewrite was needed.

Checks: `py -m unittest test_rowset_scores test_rowset_integration`, `node test_custom_filter_visuals.js`.

## Sharing address and public links (0.24.0)

At the top of **Administration → Server domain and port**, set the sharing domain (a hostname or IP address), HTTP/HTTPS protocol and optional sharing port. **New invitation links and public links use this address immediately after saving; changing only the sharing address does not require a restart.** For `https://reports.example.com`, use domain `reports.example.com`, HTTPS and sharing port `443`. For `http://reports.example.com:8765`, use HTTP and sharing port `8765`. A blank sharing port follows the listening port. Existing copied URLs retain their original address; generate new links to use the new address. No host value from an incoming request is used to generate links.

The server listening port and interface are separate settings and apply on restart. The default remains `127.0.0.1:8765`; changing a sharing domain alone does not expose a local listener to the network. Use an appropriate network interface or reverse proxy, and configure DNS, firewall rules, HTTPS and Docker port mappings separately. A reverse proxy can terminate HTTPS while the app listens on HTTP internally. The optional sharing port supports different public/internal ports. Persisted settings live privately in `security/server-address.json`; before the first save, `D2PBI_BASE_URL`, `D2BI_PORT` and `D2BI_BIND_HOST` supply deployment defaults. The startup origin is also used for federated callbacks and cookie settings, so update provider redirect registrations before restarting with a different address. Remote federated sign-in requires HTTPS. If the app itself serves HTTPS, its certificate must cover the domain; enabling the certificate still requires restart.

Choose **Share report → Public links** to create a repeat-use, anonymous read-only link, optionally expiring after 1, 7 or 30 days. Owners and administrators can create and remove public links. The confirmation explicitly covers both the report and its queryable semantic-model data: anyone holding a public URL can view, filter and query that report without an account. Public viewing does not grant access to other reports, account administration, uploads, sharing changes or download/export endpoints. It does not create a local account or change a signed-in user's saved reading position. Hidden pages are omitted for public viewers; they are not a data-security boundary. Embedded HTML/snapshot reports containing hidden pages cannot be shared publicly.

**Administration → Public report links** lists every link, report, creator, creation/expiry time, visit count, last-opened time and active/expired/removed status. Remove a link to revoke further requests immediately, including pending DAX results; already displayed or copied data cannot be recalled. Report deletion revokes its public links, while replacing a report under the same report ID preserves them. Raw link secrets are shown only when created; only hashes are stored in the private account database. Links use URL fragments, with the bearer passed in a request header rather than query strings. Anonymous views remain scoped even when an administrator cookie is present. Reports with enabled RLS cannot create public links; turning on RLS also disables access through existing public links.

Checks: `py -m unittest test_server_address test_public_links`, `node test_public_links_ui.js`.

## HTML snapshots and report imports (0.16.0)

Choose **Export snapshot HTML** beside the saved-report selector to download a single offline `.html` file. Export calculates every page, including hidden pages, using each page's saved filters and current session selections. It preserves rendered SVG charts, tables, cards, numeric formatting and page navigation. It freezes results: slicers, chart cross-filtering, DAX calculations, animations and live custom-visual frames are not interactive in a snapshot. Unsupported visuals retain their explanatory messages; custom visual frames become explicit placeholders. Export has a progress dialog and Cancel control and restores the previous report page afterward. External font imports are removed; installed fallback fonts are used. No original semantic-model tables, authentication credentials or sharing settings are included. The file contains the displayed data, including any data shown on hidden pages.

Use **Browse files**, **Import report**, or drag/drop to import `.html`/`.htm` files saved with UTF-8 encoding. Both Death2PowerBI snapshots and third-party HTML with embedded data and JavaScript are supported. Each upload creates a separate report owned by the signed-in account. Snapshots remain static documents; external HTML retains its own embedded interactions. Both support existing sharing, single-use invitation links, administrator visibility and report deletion. Choose **Download HTML report** to save an imported document again. Import does not reconstruct a native semantic model from arbitrary HTML.

Imported source is returned through an authenticated JSON endpoint and inserted only in a sandboxed iframe with `allow-scripts` and an opaque origin. It cannot access the application's DOM, cookies or storage. A prepended content policy restricts resource/data requests to embedded content and disables child frames, workers, forms, objects and popups. Reports requiring external dependencies, same-origin storage, workers or application APIs may not work without source changes. Downloading an original third-party HTML document preserves its original code; the application's sandbox applies while viewing it inside Death2PowerBI.

Snapshots contain a versioned base64 JSON marker (`death2powerbi-snapshot`, version 1), validated as inert data on import. Unknown versions or malformed snapshot packages are rejected. No report scripts execute during server-side import.

Checks: `py test_html_reports.py` and `node test_html_reports.js`.

## Single-use invitation links and federation (0.15.0)

Open **Share report → Invitation links**, select an expiry (1, 7 or 30 days), then choose **Generate single-use link**. Copy the URL immediately: its secret is only displayed once. Opening or previewing a link does not consume it. An existing local user signs in with their username/password and explicitly clicks **Accept invitation**. A successful federated sign-in from an invitation claims it automatically. Exactly one account can claim each link; its report access persists after the link expires. Owners and administrators can remove links. **Accounts → All sharing links** shows every creator, report, creation/expiry time, unused/used status, recipient and use time, including removed records. Removing a used link preserves its audit record and does not revoke the recipient's access; uncheck that user in **Share report** to revoke access.

Google and Microsoft Entra ID use OIDC authorization-code flow with PKCE, browser-bound state, nonce and RSA-signed ID-token validation (issuer, audience and expiry). A first federated login requires a valid invitation and creates a non-admin local account stub keyed by issuer/subject. Later sign-ins reuse it. Emails are display metadata and never automatically link a federated identity to an existing local account. Federated users cannot use or reset a local password; they manage credentials at their provider. Administrators can see their provider and identity details and delete their account normally.

### Configure providers

No provider credentials are bundled or configured by default. Create `security/oidc.json` based on `OIDC_CONFIG.example.json`, including only the providers you enable, and protect that file with local filesystem permissions. Keep real client secrets out of source control and distribution archives. Provider buttons stay disabled until the corresponding client credentials are present. Restart after changing the configuration.

- **Google:** Register an OAuth **Web application** client, configure the consent screen/test users as appropriate, and enter its client ID and client secret under `google`. Register the exact redirect URI `http://127.0.0.1:8765/auth/callback/google` for the default local installation. Only `openid profile email` scopes are requested. Follow [Google's OIDC documentation](https://developers.google.com/identity/openid-connect/openid-connect).
- **Microsoft Entra ID:** Register a Web application in the specific tenant you want to accept, add a client secret, and enter its directory/tenant UUID, application/client ID and secret **value** under `entra`. Register `http://127.0.0.1:8765/auth/callback/entra` as a Web redirect URI (loopback registration may require the application manifest; follow Microsoft's redirect-URI rules). This implementation accepts that tenant, rather than a `common` or multi-tenant issuer. Follow [Microsoft's authorization-code documentation](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow).

For users on different computers, a loopback URL will not reach your installation. Run behind an HTTPS reverse proxy, set `D2PBI_BASE_URL` to its exact origin (for example `https://reports.example.com`), and register `${D2PBI_BASE_URL}/auth/callback/google` and/or `/auth/callback/entra` at the providers. Open the app through that origin before federated sign-in. The Python server continues to bind only to loopback; HTTPS termination, DNS and reverse-proxy deployment must be configured separately. The configured public origin is added to the server's Host/Origin allowlist, and cookies use Secure when that origin uses HTTPS. Do not put an application path, query or fragment in `D2PBI_BASE_URL`.

Real provider authorization requires your app registrations, outbound HTTPS connectivity and user sign-in/consent. Local signed-token protocol tests cover both providers. Live Google and Entra sign-in were also verified on October 18, 2026 in the installed local copy, including federated stub creation, invitation redemption and shared-report data access. The distribution contains no credentials; other installations must configure their own registrations.

## Share reports (0.14.0)

Select a saved report and click **Share report** beside the report selector. Check the user accounts that should have access and click **Save sharing**. Reopen the same dialog and uncheck an account to revoke access. Report owners can share their own reports; administrators can manage sharing for every report and already have access to all reports.

Recipients click **Refresh list** (or sign in again) to see reports labeled **Shared by [owner]** alongside their own reports. Sharing grants access to the complete imported model: recipients can view pages, interact with visuals, explore tables, run SQL/DAX queries and download exports. It does not grant deletion, ownership, account administration or permission to reshare. There is no row-level or page-level sharing restriction. Changes apply to subsequent server requests; already displayed data and downloaded exports cannot be recalled.

Embedded custom visual packages are available while the report remains shared. Revoking access removes that package access unless another shared report or a separate package import also grants it. Deleting a report removes its shares. Deleting an account removes its received shares and transfers its owned reports to admin, preserving other recipients' shares. Sharing is saved in the existing private SQLite account database and survives restarts. Existing reports remain private until explicitly shared.

## Visual fixes (0.13.1)

Automatic date hierarchy axes now support Year/Quarter/Month/Day through the imported active local date-table relationship. Expanded axes beginning with Year use a chronological date bucket at the deepest displayed level, keeping different years separate. Unrecognized or ambiguous hierarchies still require mapping.

Slow DAX evaluations no longer hold the application-wide lock while executing, so independent tables and custom visuals can load concurrently. Changing report pages cancels obsolete browser requests, and visuals show a loading message while waiting. Table scrolling now fits the available visual height. Existing saved reports work without reimporting; restart the updated server and refresh the browser.

## Run

Python 3.10–3.13 recommended.

```powershell
python -m pip install -r requirements.txt
python server.py
```

Open http://127.0.0.1:8765. The local server serves the same interface and all data processing. The hosted static version is an example workspace and directs imports to the local service; it has no Python extraction backend.

On Windows, double-click `start.cmd` to install requirements and launch. No hosted deployment was completed in this build. See `VALIDATION.md` for tested paths and limitations. If Polars is unavailable, PBIP CSV/Parquet imports can use the DuckDB fallback.

Only one server can use port 8765. If Death2PowerBI is already running, startup prints its address and exits successfully. Open the existing app. To restart after changing server code, press Ctrl+C in the original server terminal before starting it again. If another application owns the port, startup reports that conflict without a traceback.

Use **Shut down server** in the top bar to stop the service after confirmation. Saved reports remain on disk; restart with `start.cmd` or `python server.py`, then refresh the browser. Use **Delete report** beside the saved-report selector to permanently remove the selected import after typing its filename. This deletes its uploaded copy, metadata, Parquet and DuckDB files; it does not delete the original file in Downloads or other imports with the same filename. Deleting the last import returns to the example workspace.

## Sign in and accounts (0.13.0)

On the first launch, the application creates exactly one default account:

- **Username:** `admin`
- **Default password:** `Death2PowerBI!`

Open http://127.0.0.1:8765 and sign in. Click your username in the top bar to **change your password** or **sign out**. Changing a password requires the current password and signs out all sessions for that account; sign in again with the new password. Passwords must be 8–256 characters. Existing passwords are retained across server restarts; the default password is only used when initializing a new account store.

Admins can open **Accounts** to list accounts and their report counts, create normal or administrator accounts, reset passwords, and delete accounts. A password reset revokes all of that account's sessions. The built-in `admin` account and the currently signed-in admin cannot be deleted. Deleting another account requires its exact username and **transfers its reports to admin**, preserving the files, while revoking its sessions. Recreating a deleted username creates a different account and does not restore access to transferred reports.

Each new upload belongs to its authenticated uploader. Normal accounts can list, query, calculate, export and delete only their own reports; another account's report ID does not grant access. The admin can access all reports. In the UI, **Reports owned by** defaults to **My reports**; admins can select **All accounts** or another report owner. Importing the same filename never overwrites another account's report. Reports saved before accounts were introduced belong to `admin` automatically, with no data files moved or replaced. Only admins can shut down the server.

Custom visual uploads and embedded report packages are also restricted to the owning account, with admin access to all packages. Identical package code can be deduplicated on disk while access grants remain separate. Browser report selection, chart settings and custom-visual settings are scoped by account; signing out clears loaded report data and visual frames.

Accounts, salted **scrypt password hashes**, revocable eight-hour sessions and ownership records are stored in `security/accounts.sqlite3`. Passwords are not stored as plaintext. Sign-in uses an HttpOnly, SameSite=Strict session cookie; authenticated POST requests also require the session's CSRF token. Failed login attempts are throttled. There is no self-registration or forgotten-password email flow; an administrator resets passwords.

Back up **security/** together with **data/** and **custom_visuals/** to preserve accounts and ownership. These runtime directories are excluded from distribution ZIPs and source control. The server remains bound to `127.0.0.1` over local HTTP; account authorization protects the web application, not operating-system file access, and does not implement original Power BI row-level security.

## Import

- **PBIX (preferred):** PBIXRay reads embedded VertiPaq tables; Polars writes Parquet; DuckDB creates queryable tables. DirectQuery/live-only or protected files may lack extractable data.
- **PBIP:** Select the complete project directory, or ZIP it. Include report and semantic-model directories. Include `.pbi/cache.abf` if available, or CSV/Parquet exports named for their model tables. A `.pbip` file alone is a pointer. M refresh is not implemented.
- Reports: legacy `Report/Layout` and `report.json`; enhanced PBIR page/visual JSON. Multiple reports in one ZIP are not separated into distinct workspaces.

## Honest compatibility boundary

### Scatter, strip, ternary and maps (0.9.0)

Use **View as**, then expand **Chart fields** to configure these views from the fields returned by the visual's query:

- **Scatter plot:** distinct numeric X and Y, optional nonnegative bubble size, color and point identity. Drag to zoom/pan through Vega's interval selection.
- **Strip plot:** one numeric value and optional category/color. Raw unaggregated queries retain duplicate observations. Existing aggregated queries still plot their result rows, not the original fact rows.
- **Ternary chart:** three distinct nonnegative components with positive totals. A layered Vega-Lite construction normalizes each point to 100%, draws the triangle/grid, and shows raw values plus shares. Zero/missing/non-finite totals are omitted with a visible note; negative components are rejected.
- **Point map:** numeric latitude/longitude in valid degree ranges; optional size, color and point identity. No geocoding or external map service is used.
- **Country map:** country names or ISO alpha-2/alpha-3 codes and one numeric value. Uses country boundaries and requires one query row per country. Unmatched countries are listed rather than silently assigned a location. State/city choropleths and custom GeoJSON uploads are not implemented.

Natural Earth 1:50m geography is bundled locally with 242 features; source, hash and public-domain terms are in `dist/vendor/geography-source.json`. Field mappings are saved per report/visual/view in browser storage. They select among returned columns and do not add new model fields to the original Power BI query. Point, strip, ternary and map selections cross-filter other visuals when their identity field is directly bound to a model column.

### Chart cross-filtering (0.8.0)

Click a discrete chart category to filter other visuals on the same page. Click that selected category again to clear it; Ctrl/Cmd-click toggles additional categories. Click empty plot background to clear that source chart's selection, or use the selection chips / **Clear selections** above the page. The source chart excludes its own filter and dims unselected marks so other categories remain available. Selections from different charts combine with slicers and report/page/visual predicates. State is scoped to each report/page for the browser session and is cleared on reload.

Selections use original table/column identities and exact category/series tuples, including NULL values; they are not inferred from display labels. Imported PBIR `NoFilter` rules are honored. `HighlightFilter` rules use explicitly labeled cross-filter mode; true partial cross-highlighting is not implemented. Supported sources are charts with a single directly bound category and optional series/legend field. Histograms, box plots, scatter plots, measure-only fields and multi-field hierarchies are not selection sources yet. Existing unsupported-DAX limits still apply to target visuals. Interactions work with both imported reports and the example workspace.

### Vega-Lite renderer (0.7.0)

Imported charts and example charts now render with locally bundled Vega 6.4.0, Vega-Lite 6.5.0 and Vega-Embed 7.3.0. No Node.js installation or CDN access is needed to run the app. Version pins, source URLs, SHA-256 hashes and BSD licenses are included in `dist/vendor/`.

Chart mappings include clustered/stacked/100% bars and columns, multiple series, line/area, pie/donut, scatter, combination charts, heatmaps, histograms, box plots, waterfalls and funnels. **View as** switches among mappings compatible with the returned data and remembers the choice in this browser. Histograms and box plots summarize current query-result rows; they do not automatically request an unaggregated fact table. Matrices remain flat data previews. Waterfall breakdowns, custom Power BI visual execution, general DAX and exact source formatting remain separate limitations.

The renderer uses the existing model/query/filter translator, so its correctness boundaries still apply. Axes, legends, tooltips, negative values and resizing use Vega-Lite. Query previews are limited to 1,000 rows, with an explicit truncation notice. Small browser panels retain a horizontally scrollable report canvas. The saved single-value source slicer selection is now displayed correctly, including Life in Europe's saved 2008 year. Chart views are finalized on navigation to release resources.

Version 0.6.0 retains active and inactive relationships involving calculated tables. PBIXRay 0.15.5's public relationship list excludes tables with nonzero SystemFlags; the included adapter reads raw relationship endpoints and retains those present in the converted model. Existing stored PBIX models are repaired on loading the report library. Tables, Parquet files and DuckDB data are not reconverted. The adapter uses version-specific PBIXRay internals, so keep the pinned dependency; unavailable metadata produces a verification warning rather than a claimed complete model.

The chart translator supports fact-to-dimension joins across active many-to-one/one-to-one relationships. Genuinely disconnected categories retain disconnected-total semantics with a warning; joins are never inferred from matching column names. A category-source override is available for genuinely disconnected categories and is stored locally in the browser. It changes the visual query, not the source PBIX. Multiple fact-table measures and reverse many-side projections still need separate aggregation plans.

Cards support multiple values; matrices have a flat data preview. Source sorting is preserved. Common measure aliases, COUNTROWS and DIVIDE over simple measures/literals are supported alongside simple aggregates. Full DAX and exact Power BI formatting remain out of scope.

This is a working foundation, not a Power BI-compatible runtime. It preserves page positions, measure source and extracted relationships. The renderer supports basic cards, tables, bar/column/line charts, text, simple shapes and single-selection dropdown slicers. Categorical, comparison, NULL and logical source predicates translate to SQL, with filters propagated through extracted active many-to-one relationships using EXISTS. Report, page, visual and current-page slicer filters combine; empty filter-well/drill-through definitions do not create predicates. Source sorts on projected fields are applied. Simple aggregate DAX measures and percent-of-total aggregate expressions are supported; complex DAX still requires explicit SQL mappings. Unknown conditions fail closed with a specific explanation. Styling and chart orientation may differ. Full DAX/M, themes, bookmarks, original interaction rules, cross-page slicer synchronization, multi-select/date-range slicers, images and general filter context remain unsupported. The original visual JSON is retained in the exported manifest for future mappings.

For trustworthy analysis, use the model explorer and SQL queries and validate decoded values against the original report. No real user PBIX was supplied with the initial build; extraction compatibility for your files must be verified.

## Storage & limits

Everything is stored in `data/<model-id>/`: source upload, manifest, Parquet tables, DuckDB database. Export downloads converted files. Delete that directory to remove an import. Use the Saved reports dropdown to switch between all imports. Each upload gets its own import ID, metadata, Parquet files and DuckDB database, including uploads with identical filenames. The dropdown shows import time and an ID suffix to distinguish copies. Your active report is remembered in browser local storage; page/tab position is remembered per report during the session. Refresh list reloads saved imports without converting their models again.

1 GB (1,073,741,824 bytes) upload limit, 2 GB expanded ZIP limit; conversion currently materializes one table at a time and may need substantial RAM. SELECT queries run read-only with external access disabled, 512 MB DuckDB memory, 10 second timeout, and 1,000 row limit.

The service binds only to 127.0.0.1 and rejects foreign browser origins on writes. Do not expose it on a network. It does not enforce Power BI RLS/OLS, tenant isolation, authorization roles, or provide production multi-user hosting. Original uploads can contain credentials or sensitive metadata; keep the data directory private. Import trusted files only. A production version needs isolation and background workers for uploads/conversion, authentication, storage quotas, job cancellation and fuller query translation.

## Technology references

- https://github.com/Hugoberry/pbixray
- https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-report
- https://duckdb.org/docs/stable/
- https://docs.pola.rs/


## Version 0.10.0: numeric formats and Python DAX

PBIX column and measure format strings are now retained, including existing saved reports (metadata is refreshed without replacing converted data). Common numeric formats preserve percentages, decimal precision and thousands separators in cards, tables, numeric chart axes and tooltips. Chart values remain numeric for interactions. Advanced charts use field formats where their original field titles identify numeric channels. Mixed-format series retain their individual tooltip formats. Arbitrary Excel-style custom formats, currency literals, dynamic format expressions and locale-specific formatting are not fully implemented.

Measures exceeding the SQL translator can now use a bounded Python AST evaluator with DuckDB data access. This is an interpreter, not generated Python executed with eval/exec. Supported constructs include VAR/RETURN, arithmetic, comparisons, AND/OR operators, FILTER, SUMX/MINX/MAXX/AVERAGEX, common column aggregates, COUNTROWS, IF, DIVIDE, COALESCE, BLANK/ISBLANK, ABS and ROUND. Variables preserve the context in which they are evaluated. FILTER and iterators supply row context. Page/report/slicer/chart selections and grouped dimension filters use the existing active relationship filter paths.

The supplied Life Satisfaction Change expression was verified with the saved Life in Europe model as a scalar and grouped by Countries[Country]. Synthetic regression cases cover positive and negative changes, restricted years, single-year zero and no-data blanks. The saved Cultural Activity table was verified in the browser to show 24.20% and 81.77%. All 33 existing chart mappings continue to compile and render SVG.

This is a supported subset of DAX: CALCULATE/context transition, time intelligence, expanded-table semantics and arbitrary iterator measure references remain unsupported and report an explicit error. Python execution is limited to 1,000 groups, 50 projections, 100,000 rows per table/context, an operation budget and an eight-second evaluation budget; DuckDB statements have a ten-second interrupt. Large models should narrow their filters. Run `py test_dax.py` and `node test_formats.js` for the new regression checks.


## Version 0.11.0: reference-driven DAX expansion

The Python interpreter now registers 185 bounded DAX functions. It includes CALCULATE/CALCULATETABLE with structured filter contexts, iterators and measure context transition, SUMMARIZE, SELECTEDVALUE, ALL/ALLSELECTED/KEEPFILTERS, scope checks, relationships, rankings, text/math/date/financial/path functions, statistics and basic classic time intelligence. Compatibility lists the live function registry and links the detailed limits. See [DAX_SUPPORT.md](DAX_SUPPORT.md) for family analysis, supported overloads, semantic limits and validation; `dax-function-catalog.json` records the reference inventory. The 0.10.0 limitation text above describes the previous version.

New checks: `py test_dax_reference.py` (every registered function), `py test_dax.py` (original change measure). Existing numeric formats, chart renderer and interaction checks remain in place. Unsupported functions and operation/time limits still produce explicit errors; this is not a complete DAX engine.


## Version 0.12.0: custom Power BI visuals

Self-contained PBIVIZ packages can now be imported in Custom visuals and used by GUID in report pages. Existing report-embedded bundles are discovered automatically. A sandboxed host supplies table/categorical/grouped-series data, lifecycle, base formatting, tooltips, selections/cross-filtering and local property persistence. External network resources are disabled unless the user enables the package's declared HTTPS domains.

The original supplied Gantt, Bar Race and Topology Map bundles were verified in the browser, including Gantt cross-filtering, animated time frames and offline topology geometry. Power BI Releases Page 7 was also verified with its real embedded Gantt. See [CUSTOM_VISUALS.md](CUSTOM_VISUALS.md) for capabilities, version pinning, trust/network behavior and remaining host API limits. Run `py test_custom_visuals.py` and `node test_custom_dataview.js` for the new regression checks. Earlier statements that custom visuals are wholly unsupported describe prior versions.


## Table formatting and local sorting

Native table headers support local ascending/descending sorting of the currently loaded rows. Sorting uses the visual's in-browser result cache and does not query DuckDB. Raw values determine order, so percentages and formatted numbers sort numerically. Source table colors and supported conditional icons remain attached to their values after sorting. Preview row limits still apply.

## Python DAX calculation budgets

Each visual now has a shared **60-second** DAX evaluation budget and a **5,000,000-step** budget. Supported scalar and grouped iterator expressions can execute through DuckDB SQL, with Python evaluation retained for unsupported plans. Calculation-limit messages distinguish time from steps and show elapsed seconds, evaluation steps, the measure/field and group being evaluated. Successful `/api/dax` responses include an `evaluation` diagnostic object. Resource-limit failures show **Calculation limit reached**, rather than Needs mapping.

Server environment variables `D2PBI_DAX_SECONDS` (positive, at most 300) and `D2PBI_DAX_STEPS` (positive integer, at most 100,000,000) override these defaults. Set them before launching the server. The DuckDB interrupt for `/api/dax` follows the Python budget plus two seconds; ordinary `/api/query` keeps its 10-second interrupt. The time budget is cooperative: checks occur during interpretation and after each group, with DuckDB interruption as an additional backstop. Group, field and row limits are unchanged.

LearnPowerBI Executive Summary was tested with saved page/report filters. The bar, column and utilization-card queries passed concurrently in 7.6–8.4 seconds, about 357,000 steps each. The unrendered KPI query hit the original eight-second time budget and completed at roughly 21 seconds with the new budget. This does not add KPI rendering support. Additional interactive filter selections and machine load can change these timings. Regression checks: `py test_dax_budget.py`, `py test_dax.py`, `py test_dax_reference.py`.


## Bar and column data labels

Bar and column charts now read the imported visual's default `labels`/`dataLabels` settings. Explicit show/hide settings, model number formats, label decimal precision, fixed display units, literal colors, font size/family and inside/outside placement for clustered bars/columns are supported. Stacked labels use segment centers; 100% stacked charts display segment percentages. Null labels are omitted and negative labels follow their bars. Theme-based colors fall back to the application label color; per-series/conditional overrides and exact Power BI collision/layout behavior are not yet reproduced. The SVG text is preserved automatically in new snapshot exports; previously exported snapshots remain unchanged. Run `node test_vega.js` for rendering checks.


## Offline country locations in maps

Point maps (`map`/`pointMap`) can now use a Country/Location field without numeric coordinates. A complete explicit latitude/longitude pair takes priority. Otherwise the renderer matches country names, ISO alpha-2/alpha-3 codes and common aliases (such as UK and Türkiye) against the bundled Natural Earth geography. It derives a representative location inside the largest country polygon; these are approximate country locations, not street addresses or capitals. No external geocoding requests or API keys are needed. Country can also be chosen under Chart fields. Existing size/color mappings and cross-filtering retain the original country value.

Unknown, blank and ambiguous names are omitted with visible warnings; bare Congo and Korea require a more specific name or ISO code. Countries/territories absent from the bundled boundary dataset cannot be resolved. In the supplied Life in Europe report, Gibraltar and Svalbard and Jan Mayen are flagged as unmatched. Coordinate pairs with invalid ranges or incomplete mappings still report explicit errors instead of silently using different locations. The existing filled-map matcher shares the country aliases. New snapshot exports preserve rendered maps as SVG.

Checks: `node test_advanced.js`, `node test_vega.js`, `node test_interactions.js`.


## Map navigation

Point and filled maps now include **+**, **−**, **Reset**, directional pan buttons and a zoom percentage. Zoom controls share the automatic fitting bounds, including local coordinate extents. Drag the map to pan; a drag does not select a country. When the map has keyboard focus, use +/− to zoom, arrows to pan and Home to reset. Normal marker/country clicks continue to cross-filter other visuals. Reset affects the viewport, not report filters.

Views are remembered per account, report, page and visual for the current browser session, including page switches, filter refreshes and snapshot export. Reloading the application resets remembered views. New snapshots include the current zoomed/panned SVG view without live navigation controls. No external mapping service is used.

Checks: `node test_map_navigation.js` verifies projection updates, reset, clipping and restored/limited viewport settings for point maps and filled maps. Existing advanced-chart, chart-rendering, interaction and HTML tests remain applicable.


## Native KPI visual replacement

The supplied **Native Style KPI 1.0.0.1** package is bundled with the application and available to all signed-in accounts, without a separate upload. Native Power BI `kpi` visuals automatically map Indicator → Value, TrendLine → Trend Axis, and Goal → Target at rendering time; stored report definitions are unchanged. Optional target/trend fields are supported. The custom visual provides the latest-period callout, target comparison, status and shaded trend. Existing page/report filters, slicers and supported DAX evaluation apply.

Compatible native indicator font/precision/display-unit settings, goal settings and status settings are adapted, and model numeric format strings are retained. Month names use calendar order through a small bundled compatibility hook reading host-supplied category ordering; the original PBIVIZ in Downloads is unchanged. Date/numeric trends follow the package's existing sorting. Other textual trend labels retain the package's lexical sorting. Unsupported native formatting properties retain the custom package defaults. KPI queries exceeding the 1,000-row preview limit fail explicitly rather than claiming a latest value from a truncated trend.

The built-in component runs in the existing opaque-origin custom-visual sandbox, with no external privileges requested. Bundled component access does not grant access to other users' uploaded visual packages or reports. As with other live custom visuals, static HTML snapshots currently show an explicit placeholder for this frame.

Tests: `node test_native_kpi.js`, `py test_builtin_kpi.py`, `node test_custom_dataview.js`, `py test_custom_visuals.py`. Browser verification on LearnPowerBI Executive Summary showed **86%**, **Goal: 80% (+7.73%)**, a successful status icon and shaded trend. No re-import was required.


## Legacy report filters and visual queries

Empty legacy filter-pane and drill-through field slots (column, measure and hierarchy descriptors with no selected predicate) no longer block rendering. Real predicates continue to translate; unknown predicate expressions still fail explicitly. Legacy visual projections and prototypeQuery selections are normalized into queryState, resolving SourceRef aliases, names, sort expressions and container titles. Prototype query predicates are retained. Parser version 5 upgrades saved report definitions automatically without re-importing or replacing semantic-model data. Simple unqualified DAX aggregates such as `SUM([isNewHire])` resolve against the measure's home table in the SQL translator.

Verified Employee Hiring and History: New Hires charts render; Year=2014 and Month!=Dec filters remain active across New Hires, Actives and Separations and Bad Hires, while inactive filter slots impose no restriction. Each filtered date query returns eleven distinct 2014 year/month pairs. Unqualified measure columns and this report’s prior-year matrix calculations are now supported; see Employee matrix calculations below. Checks: `py test_legacy_report.py`, `node test_engine.js`.


## Employee matrix calculations

The Python DAX evaluator resolves unqualified model-column arguments against the current measure's home table. Simple model-column aggregates and base-table CALCULATE/FILTER blank tests use DuckDB instead of materializing large fact tables. This fixes the Employee Hiring and History matrices without increasing row, step or time budgets. `SAMEPERIODLASTYEAR` now supports classic continuous date-column selections, calendar-filter replacement and leap/month-end behavior; tagged/fiscal calendar overloads remain unsupported. The live registry contains 186 bounded functions.

All three matrix queries completed with 210 / 60 / 210 rows in roughly 6–9 seconds each. Thirty populated measure cells matched independently written SQL for current/prior-year counts, active employees, bad hires and ratios. Generic Python iterators still retain their existing materialization limits. Run `py test_employee_dax.py`, `py test_dax_reference.py`, `py test_dax.py` and `py test_dax_budget.py`.

## Report workspace layout

Import report, Load example, and Choose project folder are in the left sidebar. The sidebar also accepts report file drops. Use the tabs in the report header to navigate the workbench; saved-report selection, owner filtering, refresh, export, sharing, and deletion are alongside those tabs. The Semantic model tab contains the model summary cards followed by Tables, Measures, and Relationships.

## Workspaces

Each account has a permanent **My Workspace**. Existing reports appear there automatically. Select a workspace in the top header; **New**, **Rename**, and **Delete** manage your other workspaces. Names are limited to 80 characters and must be unique within your account, ignoring case. My Workspace cannot be renamed or deleted.

Imports are saved into the selected workspace. **Move report**, beside the saved-report selector, moves an existing report to another workspace. Deleting a workspace moves its reports back to My Workspace; it does not delete report files or data. Your selected workspace is remembered on this browser per account.

Workspaces are personal organizational containers, not permission boundaries. Shared reports can be organized independently by each recipient. Report ownership, individual shares, invitation links and administrator report visibility remain unchanged. Revoked report access also prevents moving/querying the report. Administrators use their own workspace organization and the existing owner filter to browse accessible reports.

## Local groups and group sharing

Administrators use **Groups**, immediately to the right of **Accounts**, to create groups, rename them, select member accounts, and delete groups. Local groups may contain both password-based accounts and federated account stubs. Names must be unique (ignoring case) and contain 1–80 characters. Empty groups are supported; nested groups and directory synchronization are not implemented.

Report owners and administrators can select groups in **Share report**, alongside individual accounts. Group sharing grants read access to report pages, filtering, SQL/DAX queries, HTML reports, exports, and associated custom visual packages. It does not grant permission to delete a report or manage its sharing.

Membership changes and grant removal are checked on subsequent server requests. Access is additive: ownership, administrator access, a direct share, or membership in another shared group can still grant access. Deleting a group removes its memberships and report grants without deleting accounts or reports. Account deletion removes its group memberships. Report deletion removes its group grants. Workspaces remain personal organizational containers.

## Importing an updated report

When an uploaded filename matches a report you can access (ignoring case), the app offers **Overwrite existing**, **Add as new**, or **Cancel**. If several reports match, choose the exact target by owner, workspace, timestamp and report ID suffix. Only report owners and administrators can overwrite. Read-only recipients can add a new private copy instead.

Overwrite replaces the uploaded source, semantic model, data, pages, formatting metadata and embedded visual associations. It preserves the report ID, original creation date, owner, direct account shares, group shares, invitation links and every user's workspace assignment. The target stays in its existing workspace, even when uploading from a different workspace. The updated manifest records a revision and updatedAt timestamp. Add as new creates a separate report in the selected workspace with independent sharing.

Replacement is converted in a staging directory before the previous contents are moved aside. Conversion or swap failures restore/retain the previous report. If that report has active SQL/DAX queries, the app asks you to wait and retry. After replacement, local slicer selections and visual mapping overrides for the replaced report are cleared so they do not reference obsolete fields. Other viewers should refresh their report list to load the updated definitions. Self-contained HTML and snapshots use the same matching workflow.

API clients can POST /api/import/check with a JSON filename for accessible matches, then submit multipart /api/import with mode=new or mode=overwrite and overwriteId. mode=auto returns a 409 IMPORT_CONFLICT if a matching accessible report exists. Omitting mode also checks for conflicts; older browser pages cannot silently create duplicate reports. Refresh an older page to use the overwrite/add choice.

## Report presentation

See [Presentation support](PRESENTATION_SUPPORT.md) for shapes, images, themes, layering, navigation, tooltips and hidden-page restrictions. Unsupported elements are omitted from the canvas; Compatibility lists their reasons.

## Exporting visual data

Hover over a data visual and open its **⋯ / Export data** control, then choose **Chart data** or **Underlying rows** and click **Download CSV**. This is available on supported charts, custom visuals, tables, cards and slicers. Decorative images, shapes and text have no query data to export.

Chart data exports the evaluated query result. SQL-backed exports include results beyond the 1,000-row preview. Underlying rows exports original columns from one selected source table, honoring report/page/visual filters, slicers, cross-filter selections and supported Top/Bottom N filters. Related facts are exported separately rather than joined into potentially duplicated rows. Internal DAX filters and virtual measure transformations are not reconstructed in underlying-row exports; the dialog explains this distinction.

Downloads preserve raw numeric values (percentages are decimal fractions), use UTF-8 CSV with a BOM, quote embedded commas/newlines, and guard formula-like text. The limits are 250,000 rows, 64 MB and a 30-second SQL budget; exceeding a limit returns an error without a partial download. Existing account/report access and CSRF checks apply to CSV exports.

## Inspecting active filters

Click **Filters** beside the report canvas dimensions to open the Filters pane. It separates **Filters on all pages**, **Filters on this page**, **Slicers**, **Chart selections**, and each visual's saved filters. Use **Visual to inspect** to focus on one visual, or hover over a data visual and click its **Inspect filters (▽)** control. Top/Bottom N, categorical inclusions/exclusions, blanks and supported comparisons have readable summaries. Expand a saved filter to inspect its original definition.

**Show active filters only** is enabled by default; turn it off to also see filter wells with All values. Slicer and chart selections update live. For an inspected visual, the pane indicates whether each chart selection affects it, accounting for the source visual and disabled interactions. Clear slicers or chart selections individually from the pane; these changes affect the current session. Saved report/page/visual predicates remain read-only. Close the pane with × or Escape.

The pane describes the current imported filter definitions and interactive state. Unsupported saved conditions are marked as untranslated. Filters inside DAX measures and external self-contained HTML report logic are not exposed by this inspector.

## Application directory and distribution

The program directory is `Death2BI`, and the distributable archive is `Death2BI.zip`. Extract the archive and run `Death2BI/start.cmd`, or open that directory and run `py server.py`. Existing report data, accounts and local authentication settings stay with the renamed installed directory.
# Visual query caching

Visual SQL and Python DAX results are cached in memory for the current signed-in browser session. Returning to a page reuses results when the report version and effective query context are unchanged. Filters, slicers, selections and bookmark changes that change the query fetch new results; returning to an earlier cached context can reuse its results. Charts and custom visual hosts are rebuilt from cached data.

The cache holds up to 256 results and approximately 64 MiB (including query keys), evicting the least recently used entries. Larger individual results are returned without being cached. Failed requests are never cached. Concurrent identical requests share one execution, including across page navigation. Report overwrite, deletion, detected version changes and sign-out invalidate relevant entries. Results are not persisted to disk or shared between accounts or browser tabs. Reloading the browser starts a fresh cache. SQL explorer and CSV exports continue to query the server directly.


## Matrix visuals and row banding

Converted Matrix visuals retain row hierarchies with expand/collapse buttons, pivot column groups, and independently evaluated grand totals. New hierarchy requests use the visual query cache. Tables and matrices preserve primary/secondary row colors and supply alternating defaults where Power BI omitted default properties. Explicit equal colors and the None preset remain unbanded. Matrix requests retain the 1,000-group preview limit; exact saved expansion states and all subtotal/layout variants remain partial.

Table and Matrix data bars are supported through shared rendering for existing and future imports, including source colors, negative values/zero axes, numeric bounds, reverse direction, hidden text and value/total scope. Bars survive local sorting and hierarchy expansion. Automatic scales use the loaded result; preview limits still apply. See PRESENTATION_SUPPORT.md for details. Check with `node test_data_bars.js`.

Matrix headers support local ascending/descending sorting of loaded sibling groups with mouse or keyboard. Children stay with their parents, grand totals remain last, and bars/banding are retained without querying again. Matrix titles are shown only when authored in the source report. These shared renderer improvements apply to existing and future imports.

Tables, like matrices, display only source-authored titles. Generated field-name headings (for example Date / Count of Index) are omitted for existing reports and future conversions.

Pie/donut labels now render source label styles (category, value, percentage), numeric precision/units and source font/color settings. Omitted label visibility uses the pie/donut default of visible values; explicit hidden labels remain hidden. Outside labels use separated callouts for small slices. Horizontal categorical legends wrap into width-aware columns rather than overflowing as a single row; pie/donut radii reserve space for legends and labels. These shared renderer changes apply to existing and future imports.

## HTTPS administration

Administrators can open **Administration** beside Groups to upload a PEM certificate chain plus its matching private key, or a PFX/P12 bundle. Supply a password for encrypted keys/bundles. The server verifies parsing, certificate dates, key matching and OpenSSL chain loading before atomically replacing the saved configuration. Failed uploads retain the previous configuration. Status shows the certificate subject, issuer, expiry, SHA-256 fingerprint, current connection and next-startup HTTPS origin. Ordinary accounts cannot access these APIs; changes require the signed-in administrator and CSRF verification.

After saving, use Shut down server and launch `start.cmd` (or `py server.py`) again. Open the HTTPS origin you configured; the default is `https://127.0.0.1:8765`. The listener stays on loopback port 8765; this feature does not expose it on the LAN. Use a hostname covered by the certificate, and a certificate chain trusted by your browser. Uploading a certificate does not install a CA or bypass browser trust checks. A reverse proxy can use a different public origin/port, but must be configured separately. Google/Entra callback registrations must be updated to the new HTTPS origin; saving here does not change those external registrations. TLS startup sets the application's base origin to the saved HTTPS origin, including secure session/flow cookies and invitation/OIDC URLs.

Certificates and keys live under `security/tls`, excluded from distribution ZIPs and report exports. The key is stored unencrypted for unattended startup; the upload password is not saved. POSIX files use owner-only permissions; Windows files inherit the security directory's ACLs. Protect that directory and backups with appropriate OS access controls. Certificate replacement retains earlier private bundles for recovery; administrators can remove obsolete bundles from disk after verifying the replacement.

HTTPS settings apply on restart, not to live connections. Disabling HTTPS from Administration also takes effect on restart. If damaged certificate files prevent startup, restore the private files or set `enabled` to `false` in `security/tls/settings.json` locally, then restart. The server refuses to silently downgrade if enabled TLS cannot load. HTTPS upload/authorization/handshake regression checks: `py -m unittest test_tls`.

## Server restart and shutdown

Only administrators see the Restart server and Shut down server buttons in the application header. Both open a confirmation dialog and both server endpoints enforce administrator access, CSRF verification and explicit confirmation. Restart closes the listener and replaces the Python process, reloading code and saved HTTPS settings. It interrupts in-progress queries but keeps reports, accounts and settings. The browser reconnects automatically (or follows the new HTTPS origin); the response includes a reconnect link if startup takes longer. Invalid saved TLS configuration rejects restart while leaving the current server running. Shutdown stops without restarting. Tests: `py -m unittest test_server_actions`.

## Federation administration

Open **Administration → Federated sign-in** to configure Google or Microsoft Entra ID. Each provider has an enable switch, application client ID and write-only client secret; Entra also requires a specific directory tenant UUID (not common/organizations). The page displays the exact callback URL for the current application origin. Register a web application and that callback URL in the Google Cloud or Entra portal, then enter its credentials here. Provider registration, consent and external callback updates are separate from this local configuration page. Identity scopes, provider-bound local account stubs and existing sharing behavior continue through the existing OIDC implementation.

Settings are validated structurally and apply immediately to new sign-ins; they do not verify credentials with the provider until sign-in. Blank secrets retain the stored secret when the client ID is unchanged. A new client ID requires its matching secret; changing an ID while disabled clears the old secret. Disabling a provider retains its credentials and local account associations, and leaves local password login available. Editing one provider preserves the other. Existing oidc.json files without an enabled flag remain supported.

Only administrators can read or change this configuration. Requests require CSRF verification; responses never contain saved secrets. Values are stored atomically in security/oidc.json, excluded from report exports and distribution ZIPs. POSIX files use owner-only permissions; Windows uses inherited directory ACLs. Use appropriate OS permissions/backups for this private configuration. Tests: `py -m unittest test_federation_settings`.

## Row-level security

Administrators can define per-report roles in **Administration → Row-level security**, assign accounts/groups, add column or current-identity rules, and preview saved policies as a user. RLS is disabled by default. Enabled RLS denies rows to unassigned users; administrators bypass policies and ordinary report owners do not. SQL, DAX and exports use server-side permitted rows; raw model downloads are blocked for restricted users. Policies survive report overwrite, and security context participates in visual cache invalidation.

This is native Death2BI RLS, not automatic execution of imported Power BI DAX roles. Active many-to-one/one-to-one relationships are supported; unsupported/ambiguous paths fail closed. Unrelated tables need their own rules. HTML/static snapshots cannot enforce live RLS. See [RLS_SUPPORT.md](RLS_SUPPORT.md) for policy semantics, performance, cache behavior, export limits and tests.

### Application branding

Administrators can use **Administration → Application branding** to change the displayed application name, slogan, sidebar background color, and shared application icon/browser favicon. Upload PNG, JPEG, WebP or ICO images up to 500 KB and 4096 pixels; images are normalized to PNG at up to 256 pixels. Save applies immediately in the current browser; other users see changes on reload. Settings persist in `security/branding.json` across server restarts. Restore default branding returns Death2BI, DIE BI DIE, the tombstone icon and the original green sidebar. This does not rename the installation directory or report content.

Table and matrix report rows support page cross-filtering: click to select/toggle, Ctrl/Cmd-click to add or remove rows, and Enter/Space on a focused row. Table identities use unaggregated model columns; measures are excluded. Matrix rows include their ancestor keys, and grand totals are not selectable. Multi-selection applies within the same matrix hierarchy level; selecting a different level replaces that source selection. Source NoFilter interactions are honored. Header sorting, hyperlinks and matrix expand/collapse buttons retain their own actions. This is shared rendering behavior for existing reports and future conversions.

Snapshot HTML exports freeze supported custom visuals through the existing isolated frame message bridge, including their SVG/HTML, styles and canvas pixels. No custom visual scripts or live frames are included. Report images, SVG image links and background images are embedded as data URLs when their servers permit browser retrieval (CORS). Assets are deduplicated per export, with a 10 MB per-image and 64 MB total image budget. Missing assets or uncapturable visuals produce notes in the exported document. Snapshots remain static; custom visual interactions, animations and data queries are not retained.

Table and matrix column headers stay pinned at the top of their own scroll area while rows scroll. Imported header colors and formatting, local column sorting, and row selection are retained. This shared behavior applies to existing reports, future conversions and newly exported snapshots. Previously exported HTML snapshots must be exported again to receive this change.

Categorical slicers preserve source dropdown/list/tile modes (including legacy Basic + horizontal orientation), single-select, multi-select-with-Ctrl and Select all settings. Multi-select dropdowns use checkboxes with Apply and Clear selection; available source search is retained. Horizontal tiles use Ctrl/Cmd-click when configured by the source. Item/header fonts and colors are retained through shared formatting. Typed categorical filters support multiple values and blanks; field-parameter selectors retain single-choice resolution. Existing imports receive these rendering improvements on reload, and future imports use the same path. New snapshots preserve the displayed slicer summary and tile appearance.

Source-enabled analytics trend lines are rendered as linear least-squares fits over the currently displayed/filtered query results. Supported line, area, scatter and column charts preserve trend color, transparency, solid/dashed/dotted style, width, front/back placement and combined/per-series settings. Numeric and date axes use their actual coordinates; categorical axes use displayed category positions. Null/non-finite points are excluded, and insufficient/constant-X data does not draw a misleading fit. This shared rendering applies to existing reports and future imports, including static snapshot capture. Power BI forecast bands remain a separate unsupported feature.

## Gallery compatibility improvements (October 23, 2026)

Parser version 13 preserves sanitized embedded SVG report artwork for new and saved imports. Rendering now resolves named theme color tokens and explicit/default visual style presets, hides complete disabled axes, preserves inverted axes and supported smooth line interpolation, and queries formatting-only FillRule measures for two- and three-stop chart color gradients without displaying those measures as chart series. Existing semantic data and sharing permissions are retained during presentation upgrades.

Validation: `py -m unittest test_svg_assets` and `node test_gallery_formatting.js`, plus existing engine, style, chart, table, matrix, slicer, snapshot and interaction checks. These changes do not imply complete support for arbitrary custom visuals or DAX-generated HTML.

## Tooltip, Button slicer and format preservation (October 23, 2026)

Report parser 14 recognizes advancedSlicerVisual as a Button slicer, retains its source field identity/sort roles and selection settings, and uses saved interaction exclusions for slicers as well as chart selections. Strict single-selection cannot be toggled off; explicit false strict selection overrides legacy singleSelect settings. Tooltip-only measures remain in hover data and are excluded from plotted series.

Semantic parser 3 preserves FormatStringDefinition expressions and resolves constant DAX string definitions as measure formats. Arbitrary dynamic format DAX is retained as metadata, not claimed evaluated. Numeric labels retain positive/negative/zero sections, currency symbols, optional decimals and scale suffixes. Explicit display units/precision override defaults; automatic units use a magnitude-based approximation, including millions for large currency comparisons. Data values remain numeric. Existing stored reports upgrade metadata from their original source without replacing data or sharing.

Checks: `node test_comparison_conversion.js`, `py -m unittest test_format_definitions test_treatas`, plus existing formatting, slicer, engine and chart suites.

### Pareto scatter plots and visual calculations

Native visual calculations now support bounded RUNNINGSUM with ORDERBY and DIVIDE with COLLAPSEALL(..., ROWS), resolved over complete grouped results before plotting. Supported inputs have one category with additive aggregates or a distinct count of that category. Unsupported expressions, cycles and truncated results fail explicitly. Filters and RLS apply to the source query. Scatter reference lines and shaded regions preserve source colors, opacity and layer placement. Semantic-query Count (2) maps to distinct count; CountNonNull (5) maps to non-null count in SQL and Python fallback.

### Plot-area background images

Chart plot-area images are resolved from embedded report resources or supported image URLs and rendered behind the chart marks within the plot bounds. Source Fit/Fill/Normal sizing and transparency are honored. The same renderer is used for existing reports, future imports and snapshot chart exports; embedded artwork stays self-contained.

### Visual titles and subtitles

Visual captions preserve source text, font, color, alignment, visibility and line breaks, and reserve layout space above the plot. Titles and subtitles backed by supported measure/aggregate expressions are evaluated separately in the visual's current filter and RLS context, without adding a plotted series. Caption requests use the existing visual query cache. ThemeDataColor references resolve to the theme data-color palette by ColorId before applying tint/shade; structural foreground/background tokens retain their separate meaning.

### Line-chart labels and stable hover layout

Line/area charts preserve supported point data labels and direct series labels, including source per-series visibility, positions, text styling and measure-backed detail text. Detail measures use the existing formatting query role so they are evaluated per group without becoming plotted series. Plot-area images track live plot dimensions. Vega autosizing no longer refits on hover updates; container resizing still triggers layout updates, with redundant size notifications ignored.

### Report page tooltips

Configured report-page tooltips resolve both modern visualTooltip and legacy tooltip assignments. Hovering sends the point's category/series identity (including supported date hierarchies and mapped chart channels), source visual filters, report/page filters, slicers and other chart selections to the tooltip page. Queries retain normal authorization, RLS and caching. Hidden tooltip pages are supplied separately for non-administrators and stay out of page navigation; ordinary hidden pages remain restricted. Native tooltip cards preserve value formatting, alignment and label visibility. Report-page tooltips replace the generic tooltip and are removed on leaving the chart or navigating away.


### Native HTML Content visuals

HTML Content visuals are recognized by their standard visual identifier and render through a built-in adapter, without depending on the package host API. Content-role measures/columns are evaluated with the report's filters and RLS. Generated HTML, inline CSS, SVG, inline scripts and nested srcdoc frames render inside an opaque-origin sandbox. External scripts, network requests, top-level navigation and forms are blocked. Markdown mode and HTML-driven model selection callbacks are not implemented. Limits: 8,000,000 content characters, 256 nested frames and 12 nesting levels. Report navigation buttons layered over HTML remain ordinary converted report elements.

BCN conversion also generalizes DAX double-hyphen comments and unary NOT, bounded EARLIER row contexts, multi-key CONCATENATEX sorting, virtual-row base lineage, date serial conversion/date formats, context-specific measure memoization and partial compound-filter replacement. The default step allowance is now 5,000,000 with the existing 60-second time allowance. Measure-backed image sources are evaluated in visual context. Supported visual measure-comparison filters run after grouped evaluation; they do not become row-level SQL filters or chart series.


Report-level measures in PBIR `reportExtensions.json` are merged with semantic-model DAX measures on import and when older saved reports load. Their format strings are retained. Table SVG image measures use the authored image width and height. Clustered bar/column charts also support explicit error ranges whose bounds are projected measures, including marker shapes and transparent series used for dumbbell plots.


Additional native reconstruction includes embedded image `sourceFile` resources, page/bookmark navigators, rank ribbons, and an interactive decomposition tree with explicit split-field choices. Decomposition branches query their own scoped totals (genre memberships are not summed into an incorrect grand total); automatic AI splits are not implemented. The DAX evaluator supports CALCULATE CROSSFILTER Both/None/OneWay against existing relationships, including Both/None on many-to-many bridge relationships. Direct many-to-many aggregate joins fall back to separate DAX evaluation to avoid double-counting. HTML Content supports HTTPS poster images with no-referrer; scripts still have no application-origin access, fetch, forms, or external script loading.


Numeric Single Value slicers retain their saved scalar value and render a numeric input plus a domain-snapped slider, including percentage input. Legacy scalar starts with equality filters are recognized when the default mode is omitted. New Card values apply per-measure precision, compact display units (including automatic K/M/B/T scaling), alignment and colors. Native KPIs fit short containers and omit comparison goals when no target field exists. Imported model columns retain Sort by column metadata; default chart/category queries respect that order while explicit visual sorting still takes precedence. Series metadata names are distinguished from conditional color expressions so aliased multi-measure series keep their colors and legends.


Imported Power BI scatter plots suppress automatically generated bubble-size legends and support an omitted Y field as a single-axis dot plot. Size continues to control marker area. Complex measured Top N filters use the secured DAX evaluator before applying the visual preview limit; ties at the boundary are retained. Numeric RANKX scores over explicit ALL/ALLSELECTED column domains can be calculated together in DuckDB and reused within a request. Other ranking forms retain the bounded interpreter. Field-parameter metadata identifies the expression column from its field references, even when the source parameter points to a display-label column; selected fields, sorts and disconnected parameter filters remain synchronized. Existing saved reports refresh that metadata automatically.

DAX `FORMAT(value, mask, locale)` supports explicit locales such as `es-PY` through Babel, including localized separators and supported date names. This applies to existing saved reports and future imports. Supported masks remain bounded; see DAX_SUPPORT.md.

Rendering and calculation improvements: Decimal calculation results retain numeric JSON types; stale conditional-formatting measure references are excluded from chart queries; filled maps support continent locations using bundled Natural Earth continent metadata. RELATED lookups use request-local indexes while retaining secured sources and duplicate-key validation. These improvements apply to existing reports and future imports.

Additional report compatibility: native treemaps, combination charts with only one populated series role, grouped New Cards, and matrix sparklines. Point maps can infer valid coordinate means from latitude/longitude columns in the same table as a city/country/region field; this inference is disclosed on the visual. Invalid coordinate pairs are excluded from those means, without excluding rows from report totals. Country/region geography remains available offline. Signed pie and bubble sizes use magnitude for area, retain signed values in tooltips/exports, and display a note.

Dense Cartesian charts preserve readable horizontal category/series spacing inside a keyboard-focusable scrolling viewport. Scroll width is retained on resize and recalculated for filtered data. Existing and future imports use the same renderer. The query preview limit still applies; scrolling does not fetch rows beyond that limit.


### Additional shared visual support

Native 100% stacked area charts use normalized Vega-Lite stacks and percentage axes. Native gauges support a value, minimum, maximum and target; when no limits are supplied the gauge uses a zero-based range with an upper bound twice a positive value (at least one). Grouped New Cards and multi-row cards preserve their rows in a keyboard-scrollable container.

Hierarchy slicers load child values when a branch is expanded. Check a parent to include all descendants, or select individual child values; selections retain their complete ancestor path across related model tables. Chart small multiples use the native Rows/Columns grouping roles, repeat the shared renderer for each group and retain facet identities for cross-filtering. Large grids scroll inside their visual. Categorical line/area scales start at the first category; bar scales avoid excess outer padding when horizontally scrolling.


Azure Maps imports with an enabled bubble layer use sized circle markers, including when a stale filled-layer flag is also saved. Treemaps honor explicit label visibility and show category labels by default; ribbon charts use zero outer padding. Pie/donut charts label at most the twelve largest slices while retaining every slice, tooltip and exported data row. Unassigned scatter y-axes stay hidden, and gauges reserve space below their endpoint labels.

Table and matrix grand totals remain pinned at the bottom while headers remain pinned at the top. Table totals evaluate aggregate expressions at total grain using the active filters, rather than summing the loaded preview. Sorting loaded table rows leaves the total footer in place. Explicitly disabled table totals remain disabled.

Outside pie and donut data labels include leader lines connecting each label to its slice. The shared renderer retains the twelve-largest-slice label limit and omits leader lines for inside or disabled labels.



Conversion also supports modern List slicers and their dropdown setting, plus hidden and role-scoped visual sorts evaluated at the authored grouping level. Sort expressions do not appear as plotted series. DAX constant tables and omitted optional scalar arguments are evaluated by the shared bounded evaluator; CALCULATE accepts supported scalar Boolean wrappers such as NOT(column IN {...}).

Embedded SVG artwork retains safe CSS opacity, keyframes, media rules and embedded font data. Scripts, active SVG nodes, external resources and unsafe CSS remain blocked. This preserves decorative overlays without turning their transparent areas into opaque rectangles.



Import compatibility: BOM-less UTF-16 TMDL scripts are detected alongside UTF-8 and BOM-marked UTF-16. Embedded Shape Map TopoJSON/GeoJSON polygon boundaries are converted locally and retained for filled-map rendering, including location-name and ISO-code matching.

Dynamic SVG image data URLs normalize raw markup, color hashes and partially escaped payloads so SVG measures display in images, cards and tables. Unsupported embedded table segments produce per-table import diagnostics while preserving the report and any readable tables. Missing table data is never replaced with fabricated rows.

Native chart rendering suppresses categories whose plotted measures are all blank, while retaining zero values and explicit show-items-with-no-data projections. This applies to future imports and existing reports.

Maps accept finite latitude/longitude values stored as unambiguous numeric text without changing stored model types. Date/time FORMAT masks support localized month/day names, contextual minutes, 12/24-hour clocks, AM/PM, seconds and quoted literal text.

State/province location fields that match US state names or postal abbreviations use the locally bundled US state/territory boundaries, keeping state codes separate from country codes. Filled maps with only tooltip measures preserve uniform fill rather than inventing a color scale. Source and licensing metadata are stored with the bundled geography.

Pie/donut visuals support multiple measure slices, and measure-only native charts retain every measure. Bookmark display state supports nested visual groups, including scoped filter-panel backgrounds and controls, without resetting unspecified visibility.


Saved-report lists use compact metadata and load full report definitions on selection, avoiding transfer of every report’s embedded assets and DAX source during list refresh. Report detail endpoints retain account-sharing and RLS authorization.

Known HTML Viewer (`paraHTMLViewer` with the standard cvalue role) visuals use the same isolated renderer as HTML Content, avoiding package data-view assumptions while retaining the renderer’s network and frame restrictions.

### Import process isolation

Uploads are decoded in a separate Python worker with a 300-second limit. A native decoder failure is returned as an import error while the HTTP server and existing reports remain available. Task-owned staging files are removed after each attempt. Date decoding has a validated microsecond-resolution overflow fallback; real missing dates remain missing.

### Report colors and tooltip pages

Theme references preserve background, foreground and accent palette slots, including shades. Error-range endpoint markers render behind individual measurement markers so overlapping endpoints retain series colors. Tooltip pages render at authored size, expand to contain loaded visual content and fit as a complete page within the browser viewport without internal scrollbars. Existing reports receive these renderer fixes on browser refresh; reimport is unnecessary.

Visual queries return up to 10,000 rows (including custom visuals, matrix groups and report tooltips). Python DAX visuals accept up to 10,000 groups; evaluation time and step budgets still apply. SQL Explorer retains its separate 1,000-row preview and 10-second query timeout. Larger visual results show a truncation notice; CSV exports retain their separate export limits.

Report formatting fidelity: grouped New Cards honor horizontal small-multiple layouts, default group ordering, labels above values and card tile backgrounds. Enabled visual backgrounds use the theme background when no explicit color is supplied. Categorical charts retain category spacing and suppress blank measure categories before forming small-multiple domains; zero values remain. Numeric button slicers ignore implicit aggregate-based default ordering while retaining explicit sorts. Inspect filters and Export data appear in a hover/focus toolbar just outside the visual, independent of its scrolling container.

Scatter visuals preserve authored marker shapes and bubble sizing, with default marker opacity and explicit transparency overrides. Measure-driven fill colors are evaluated in each point context, including wildcard formatting selectors. Table foreground/background color measures are queried as hidden formatting fields, while None table styles retain unbanded transparent rows and authored cell colors and widths. These behaviors apply to existing reports and future conversions through the shared renderer.

Static visuals, including text boxes, preserve enabled Title and Subtitle text and their fonts, colors, alignment and visibility settings. Caption-only text boxes are retained even with an empty paragraph body; body text remains separate. Supported measure-based captions on static visuals evaluate under the same report/page/slicer context as chart captions. These rules run in the shared renderer for existing imports, future conversions and snapshots.

Card display precision follows authored model/projection formats, including abbreviated K/M/B values. Explicit visual decimal settings take precedence; a default precision is used only when no format is supplied. For disconnected category tables, supported aggregate query plans compute the fact-table total once before expanding category domains. Each category receives the same total under the independent fact filters, with the existing missing-filter-path notice retained.

Horizontal bar visuals with more categories than fit vertically use a scrollable window of cached rows. Bars retain readable row spacing, visible labels, category order and a consistent value axis across scrolling; scrolling does not issue a new database query. Tied source value sorts include a stable category tie-break. Chart currency labels/axes preserve currency symbols, scaled display units (including trillions), explicit decimal overrides and compact automatic precision. New Card fills resolve per-projection fillCustom and cardCalloutArea settings before fallback backgrounds.

Canvas/background images honor Stretch and the legacy canvas Fit scaling value as full-bound stretching (100% width and height); Contain and Normal remain separate modes. Slicer Header and visual Title have separate text, styling and enabled states. A disabled Title never suppresses an enabled Slicer Header, and a disabled Header never suppresses an enabled Title. Shared caption rendering retains this behavior for existing reports, future conversions and snapshots.

New Card text honors textWrap, preserves line breaks, and is constrained to the authored visual width. Internal card padding resolves per-card margin settings. Disabled source card borders override default tile border styles, independently from decorative report artwork. These shared rendering rules apply to existing imports and future conversions.

Shapes and navigation buttons support enabled Text properties bound to measures or single-valued columns. The scalar text query uses report, page, slicer and cross-filter context and the existing security-aware cache. Shape text preserves escaped content, line breaks, font, color, alignment and wrapping; navigation actions remain independent of the resolved label. Disabled Text properties do not query or display retained text.

Native scatter charts use standard endpoint-preserving sampling: unplottable X/Y values (null, nonnumeric or nonfinite) and invalid configured sizes are removed before choosing up to 3,500 evenly spaced points, retaining the first and last valid rows. Sampling is deterministic in query-result order, preserves point identities/formatting and does not alter cached query rows or exports. This is the renderer fallback for already materialized results. SQL-backed scatter visuals use the full-result high-density path below.

SQL-backed scatter charts now query the complete secured/filtered SQL result without the 10,000-row visual preview cutoff, retaining the 10-second database timeout. The server uses a deterministic 32×32 spatial grid to select up to 3,500 original rows: occupied cells receive representatives and remaining slots follow cell populations. First/last points and X/Y extrema are retained. Invalid axes/sizes are excluded. The response carries full-result counts and regression statistics, so combined trend lines use all valid rows instead of fitting only the sample. Other visual and SQL Explorer limits remain unchanged; Python DAX grouping remains separately bounded. The sample is an approximation, not a density heatmap.

Deneb visuals can display HTTPS image URLs present in their query results without enabling general network access. Custom visuals that supply row identities to the tooltip service can display their configured report-page tooltip, filtered to the hovered data point. These shared rendering changes also apply to previously imported reports.

New Card multi-card layout preserves Arrangement (horizontal, vertical, or grid), including theme settings, explicit grid column/row counts, and the default horizontal arrangement. The shared renderer applies this to existing reports and future imports.

Treemaps preserve independent Category labels and Data labels visibility. Category text uses its own formatting; Colors settings support explicit category assignments and field-value conditional colors, including aggregated column values. Shared styling resolves formatting projections by model field name and supports the treemap Group role.

Card and New Card visuals display assigned report-page tooltips on hover. Scalar cards retain report/page/visual/slicer context without inventing a category filter; grouped cards also pass their hovered group values. Disabled or unassigned tooltips are not attached, and tooltip-page cards do not recursively open more tooltip pages.

Bookmark display restoration treats a saved visual with an omitted display mode as visible, as Power BI does. Explicit hidden states, scoped targets, and inherited group visibility remain respected. This also fixes reveal buttons whose target visuals start hidden.

Administration includes an Allow sandboxed custom visuals to load any HTTP/HTTPS image URL checkbox in Application branding. It is disabled for clean installations; reload reports after changing it. Only image loading is broadened: script, connection, iframe and form restrictions remain. Image hosts receive normal browser image requests. Native URL images load eagerly and no longer remove their visual after a transient load failure. Custom dark themes derive compatible table stripe/header colors when those colors are omitted instead of inheriting white stripes from the base theme. Ordered measure filters exclude blank values, and compact bar charts fit up to six categories before enabling scrolling.


## Shared compatibility foundations (2026-10-25)

Report imports now use a pinned offline bundle of 28 Microsoft JSON schema documents. Supported PBIR/PBIP revisions are validated without fetching schema URLs supplied by reports. Unknown revisions/properties remain preserved and are described, with file/property paths, on Compatibility. Legacy aliases normalize into the shared representation without mutating the input definition. Installed native reports upgrade presentation metadata from their retained source; converted data and access settings remain intact.

Formatting resolution distinguishes omitted, false, null and explicit values; combines base/custom theme, preset, visual/container and selector/state overrides; and can report the winning source. Source theme colors remain unchanged. A contrast fallback for an unreadable inherited base-theme table stripe is a renderer fallback, recorded on Compatibility; an explicitly assigned stripe color is preserved. Card and chart element settings use the shared property resolver.

Numeric/date display supports model, visual and element precedence, common VBA/.NET masks, report locale, decimal precision and display-unit controls. Dynamic measure format expressions are evaluated separately from numeric results using the same group/filter/RLS context. The stored expression is interpreted by the bounded DAX evaluator, never executed as Python source. Cards, native chart value labels/tooltips, tables and matrix values consume per-row formats. SELECTEDMEASURE, SELECTEDMEASURENAME and SELECTEDMEASUREFORMATSTRING are available in format-expression context. Unsupported format expressions produce a warning and use the static format; unsupported DAX semantics remain subject to DAX_SUPPORT.md. Full .NET/VBA formatting engines and calculation-group execution are not claimed.

DAX BLANK comparisons retain loose/strict semantics. Visual nonempty suppression is separate, preserves numeric zero, and respects show-items-with-no-data projections. Bookmarks plan changes before committing them, honor Data/Display/Current page/selected-visual options, include scoped group descendants and multiple saved sections, and preserve projection formatting metadata. Custom/native chart tooltips and chart selections carry compound column/hierarchy/series/facet identities instead of identifying a point by a single display label.


## Complex iterator and optional-formatting reliability (2026-10-25)

Visual data queries now evaluate optional color/label/reference-line measures separately. A failed optional expression produces a diagnostic warning and leaves the chart data available; unsupported reference lines are omitted. Supported formatting expressions retain the exact visual group and filter context.

The shared DAX evaluator lowers supported numeric FILTER/iterator expressions, ordered CALCULATE predicates, nested measures, and column-lineage ADDCOLUMNS into DuckDB. Explicit table-filter arguments are captured before ALL/REMOVEFILTERS modifiers; Boolean column filters enumerate their independent secured domain; row transitions preserve expanded relationship context. Repeated grouped aggregate thresholds and relationship lookups are cached within an evaluation. FILTER over ADDCOLUMNS evaluates conjunct-dependent extensions in stages, and large group domains use typed Arrow input rather than per-row insert statements. Complex nested row transitions retain bounded scalar groups to avoid oversized combined SQL plans. Unsupported forms keep the bounded interpreter fallback. Existing RLS and evaluation budgets remain in effect.

These changes apply to installed reports and future conversions without altering stored source DAX or report data. Nested iterator ALLSELECTED shadow contexts remain unsupported and are reported explicitly.

## Report behavior and visual fidelity

Version 0.22.0 adds shared cross-highlighting, synchronized slicers, automatic report-tooltip bindings, drillthrough/category drill controls, expanded field parameters, consistent conditional formatting, hierarchical matrix improvements, source-aware chart layout and report locale defaults. See [Priority 2 support and boundaries](PRIORITY2_REPORT_BEHAVIOR.md) for usage, validation and compatibility limits. Existing reports acquire updated presentation metadata on their next load; their semantic data and source measures are preserved.


## Context-aware DAX performance (0.22.1)

Supported CALCULATE not-equal predicates execute in DuckDB with case-insensitive text and blank-aware comparison. Nested FILTER SQL retains the original table scope when filtering its source, avoiding accidental correlated subqueries. Deterministic scalar CALCULATE bodies are reused within one evaluation after their filter context is established, including selected-domain extrema. The bounded cache distinguishes external selections, scope, row contexts, lexical variables, relationship overrides and selected-measure context; volatile expressions and opaque user functions are excluded. Results are never shared between requests or users.

Dynamic axis limits and reference-line values are evaluated once in the visual's report/page/slicer context rather than once per plotted category. Per-point formatting remains grouped. These shared query/rendering changes apply to existing reports and future imports without reconversion. Evaluation limits remain 60 seconds and 5,000,000 steps by default; optimization does not disable RLS or rewrite report measures.


## Iterator, scatter and one-sided slicer compatibility (0.22.2)

Boolean CALCULATE predicates retain their independent column domains when other columns filter the same table. Literal/variable comparisons and blank tests are pushed down, avoiding repeated domain enumeration. This fixes SVG measures whose dimensions depend on a total fetched from another row. FILTER membership over a one-column table is applied in DuckDB before materializing a large bridge. Relationship context transitions load matching dimension keys on demand rather than materializing a large dimension. Supported SUMX row arithmetic and explicitly cleared key lookups can execute as a secured vector aggregate. Selected-table cumulative SUMX patterns inside ADDCOLUMNS use a window sum with ties when the complete current selection is the iterator domain. Arbitrary nested ALLSELECTED shadow contexts remain unsupported.

One-sided numeric Before/After slicers render as sliders, retain their selected boundary and emit inclusive range filters; Single retains equality semantics. Scatter reference-line and shaded-region layers do not create independent axes, preserving disabled axes and preventing Vega-Lite layered-axis failures. A consistent per-series color assignment uses a categorical color scale so legends remain visible; varying point colors remain individual overrides. Card tooltip-only and hidden-formatting projections do not create card tiles. Default card tooltip fields appear on hover, while assigned report-page tooltips keep their page renderer.

All changes run in the shared evaluator/renderer for stored reports, future imports and supported snapshots. Source DAX, report data, evaluation budgets, and RLS remain intact.


Page navigators honor per-page showPage overrides and showByDefault, including explicitly selected hidden pages for administrators. Hidden-page access remains administrator-only. Tooltip pages are detected using pageType/isTooltip as well as legacy metadata and excluded by default. These shared rules apply to existing reports and future imports.


## Resume the last viewed report and page (0.22.3)

Each signed-in account has a server-side reading position containing its last report, page ID and workspace. Refreshing or signing in from another browser restores that location instead of selecting the newest import. Navigation writes are ordered and skipped when the location is unchanged; snapshot export does not replace the user's reading position. Stored locations never grant access: the current report list and hidden-page permissions are checked again, and a missing report, deleted page or changed access falls back to an available location. The application continues using account-scoped browser state as a migration fallback when no server-side position exists. Reading positions are private to their accounts and are removed when an account is deleted.


## Bookmark groups and batched Top N filters (0.22.4)

Bookmark navigators preserve their selected bookmark group, child order and nested groups from PBIR bookmarks.json and legacy nested bookmark definitions. A grouped navigator shows only that group's available bookmarks; unrelated bookmarks are excluded. Stored report presentation metadata upgrades automatically from the retained source, so existing reports do not need to be reimported.

Measured Top N filters score their entire secured category domain in one DuckDB plan when supported. Large domains use a temporary Arrow-backed identity relation that is removed after evaluation. Fixed, disconnected SELECTEDVALUE parameter choices prune unused SWITCH branches, including VAR-bound choices; group-dependent selections remain contextual. Supported CALCULATE/CROSSFILTER and numeric MEDIANX patterns lower to SQL, including relationship-modified CALCULATETABLE sources. Unsupported expressions retain the bounded Python fallback. Top N ties, filters, source DAX, report data and RLS remain intact; the default 60-second evaluation limit is unchanged.


## Parallel DAX execution (0.23.0)

DAX visual calculations, measured Top N filters and dynamic formats now run in a bounded pool of reusable Python processes. The server starts up to two workers by default (one on a single-CPU host); each worker runs one request at a time using one DuckDB execution thread. Workers start lazily, retain imported Python modules, and open/close a separate secured database connection for every request. SQL-only visual requests retain their existing threaded route. Browser SVG/DOM rendering remains on the browser main thread.

Configure these environment variables before starting/restarting the server:

| Variable | Default | Allowed | Purpose |
|---|---:|---:|---|
| `D2BI_DAX_WORKERS` | 2, or 1 on a single-CPU host | 1–8 | Maximum simultaneous DAX processes |
| `D2BI_DAX_THREADS` | 1 | 1–8 | DuckDB threads per DAX worker connection |
| `D2BI_DAX_QUEUE_SIZE` | 32 | 0–256 | Maximum waiting requests, in addition to workers |
| `D2BI_DAX_QUEUE_SECONDS` | 120 | 1–300 | Maximum wait before dispatch |

For example, in PowerShell: `$env:D2BI_DAX_WORKERS='4'` followed by `py server.py`. In Docker Compose, add `D2BI_DAX_WORKERS: "4"` under the service's environment settings and recreate the container. Start with two workers and one DuckDB thread per worker; increasing both raises CPU and memory demand. Each database connection retains the existing 512 MB DuckDB memory limit, which is not a total process-memory cap. Workers recycle after 100 dispatched requests.

The existing `D2PBI_DAX_SECONDS` (60 seconds) and `D2PBI_DAX_STEPS` (5,000,000 steps) remain per-calculation limits. Queue wait is reported separately. A parent watchdog also bounds a complete worker job to its calculation limit plus 35 seconds for startup, RLS preparation (existing 30-second limit) and cleanup/IPC. A crashed, cancelled or hard-timed-out worker is terminated and replaced lazily without stopping healthy workers or the HTTP server. Full/expired queues return HTTP 503; watchdog timeouts return 504, and normal evaluator errors retain their diagnostics. DAX request bodies are limited to 64 MB independently of the 1 GB report-upload limit.

The server resolves authentication, report access and RLS after queueing and checks them again before returning results. A policy revision during execution discards the stale result with HTTP 409. Each worker receives only semantic metadata and a server-generated security context, never the authentication database or provider credentials. An RLS-limited request uses a freshly materialized secured database; `ALL` cannot restore forbidden rows. Connections and per-request evaluator caches are not shared between users. Reports with active queries cannot be overwritten or deleted.

Cache invalidation/aborted underlying DAX requests send an authenticated, CSRF-protected cancellation with an account-scoped request ID. Cancelling one navigation consumer retains an existing shared query for other consumers and subsequent page-cache reuse. Ordinary page changes therefore preserve the previous query-cache behavior. Explicit cancellation stops queued work or replaces its active worker. Server shutdown/restart and SIGTERM close the entire pool.

Administrators can inspect authenticated `GET /api/admin/dax-pool` for capacity, running/queued counts, worker PIDs and completion/error counters. DAX responses add `executionMode`, `workerPid`, `queueSeconds`, `workerElapsedSeconds`, `workerProcesses` and `duckdbThreads` under `evaluation`; existing calculation elapsed time/step diagnostics are retained. No settings or reports need migration.

Checks: `py -m unittest test_dax_pool test_dax_pool_http -q` and `node test_dax_requests.js`.
