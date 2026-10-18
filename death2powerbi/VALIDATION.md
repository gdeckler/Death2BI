# Build validation

## Live provider configuration (October 18, 2026)

Google OAuth Web client and an Entra single-tenant application were configured in the user's authorized projects/tenant. Both authorization startup endpoints succeeded. Browser sign-in with each real provider validated its signed ID token, created a distinct non-admin local stub, redeemed its invitation and returned sample SQL data. Verified the Entra callback persisted in the manifest and that additional Microsoft Graph API permissions were empty. Local admin sign-in continued to work after both provider tests. Removed only the temporary verification report and its invitation audit fixtures; retained the user's real federated identities. Credentials remain under the excluded security directory.

## Invitations and OIDC (0.15.0)

Integration tests cover anonymous preview without consumption, authenticated/CSRF-protected redemption, expiry, removal, deletion invalidation, audit status, blocked recipient link management, and two separate SQLite store instances racing for the same token. Locally signed RSA fixtures test Entra and Google code/PKCE exchange, browser state, nonce, issuer, audience, expiry, future-issued tokens, signature tampering, callback replay, non-admin stub creation, no email-based account merging, local-password rejection and stable returning identities. Existing account/sharing tests pass. Browser-verified generating a link, opening it signed out, signing in with an existing local account, explicit acceptance, shared-report selection and rejection on reuse. Live administrator API verification confirmed used-by/time and link removal. Removed only disposable QA report/account/audit fixtures. Live provider authentication was subsequently verified; see the October 18 configuration section above.


## Report sharing (0.14.0)

Owners and administrators can select/revoke recipients. HTTP integration tests cover private-by-default imports, persistent sharing, recipient listing/query/DAX/export access, blocked deletion/resharing, CSRF and invalid-recipient rejection, independent recipient revocation, package access revocation and report-deletion cleanup. Existing account isolation, session and lifecycle tests pass. Browser-verified saving and reopening selected recipients, then revoking a disposable synthetic report; live recipient API requests confirmed access and subsequent denial. Removed only the disposable report and test account; existing reports/accounts/shares were preserved.

## Visual fixes (0.13.1) visual regression verification

- Power BI Releases.pbix Page 2: browser renders the line chart with 86 chronological date points. Every date/count matches a direct DuckDB grouping of Sheet1, with the original 2019–2026 date-table filter applied.
- Page 4 simple table: browser renders 86 rows, sorted by distinct count descending, with its own scrolling area. The separate pivotTable's unprojected sort remains an explicit unsupported mapping.
- Page 7 Resizable Gantt: embedded package renders its 1,000-task preview, including after rapid page switching. The 1,000-row preview limit still applies.
- Regression tests cover automatic hierarchy day/month/year grain, unchanged source definitions, missing relationship rejection, and a table query completing while another request remains inside a slow DAX evaluation.
- Account isolation/lifecycle, custom visual adapters/packages, DAX reference, chart interactions and all 33 Vega-Lite chart compilation/rendering tests pass.

## Advanced plots and maps (0.9.0)

All 33 type identifiers compile and render with bundled Vega-Lite/Vega (including aliases). Tests verify ternary corner coordinates, normalized shares, invalid/zero totals, preservation of strip duplicates, configurable scatter channels, invalid coordinates, ISO-code matching, unmatched-country notices, duplicate-country rejection and point identities. Natural Earth geography is served locally. Browser-verified with a disposable imported report containing scatter, strip, ternary and point-map visuals: all render; changing scatter X to Value changes the axis; selecting France filters the other three plots to France. Removed only the disposable report after validation. Country choropleths compile/render in automated tests; boundary matching remains dependent on supported country names/codes.

## Chart cross-filtering (0.8.0)

Browser-verified using a disposable imported CSV/PBIR report: clicking North's bar kept all three source bars, reduced the target table from four rows to its two North rows, changed a filtered SUM card from 42 to 15, and left a card configured with NoFilter at 42. Clear selections restored all rows and totals. Removed only the disposable report afterward. Unit checks cover single-click toggling, Ctrl/Cmd multi-selection, NULLs, source exclusion, NoFilter, report/page isolation, clearing, and exact multi-table category/series tuples propagated through relationships. Vega rendering regression tests and JavaScript syntax checks passed. PBIR parser version 4 preserves visual interaction rules for existing and new imports. True cross-highlighting remains out of scope.

## Vega-Lite integration (0.7.0)

All 25 mapped type identifiers compile through bundled Vega-Lite and render SVG through Vega. This includes aliases of the same chart family. Tests cover multiple series, negative values, temporal/null data, empty results and rejection of invalid pie/scatter inputs. Actual Life in Europe DuckDB results render successfully; its 46-country query still passes. The running service serves all three local libraries with JavaScript MIME types. Verified in the in-app browser: the original column chart renders, View as switches to bars, the saved source selection displays 2008, and changing the year changes the plotted Germany value (2008: 81,110,734; tested 2004: 82,092,658). Restored the source year and original column view afterward. Shutdown/deletion regression tests passed using disposable fixtures. Existing semantic-model data was not reconverted.

## Calculated-table relationships and wider chart rendering (0.6.0)

Raw Life in Europe.pbix metadata verifies an active Population[Country] -> Countries[Country] relationship. Countries has SystemFlags=2, and the previous public PBIXRay relationship endpoint omitted its four relationships. The adapter now retains all 13 logical relationships rather than nine. Repaired the stored model without reconverting data. The original chart compiles with its Countries field and returns 46 country groups; all totals match independent SQL with the source country exclusions, including through the live query API. No remapping is required. Tests also cover connected/detached category plans, all 15 chart renderer types, multiple value fields, negative bars, escaped labels and area fills. HTML/JavaScript generation tests passed; browser visual QA remains unverified. Complex DAX, custom visuals, full matrix formatting and multiple-fact measures remain limited.

## Shutdown and saved-report deletion (0.5.0)

Isolated HTTP lifecycle tests passed: wrong filename confirmation and invalid IDs rejected; foreign origins rejected; deleting one of two identically named fixture reports left the other report intact; shutdown required confirmation, stopped the test service, and preserved remaining data. Library tests cover selection fallback after deleting the active/last report. JavaScript and Python syntax checks passed. The live service was upgraded to 0.5.0; no user reports were deleted during testing.

## Duplicate startup handling

Ran the updated server while the existing Death2PowerBI instance owned port 8765. It identified the healthy service, printed the app URL and restart instructions, and exited with code zero without a traceback. The existing service was left running.

## Multiple reports and stale importer fix (0.4.0)

Power BI Releases.pbix parses as seven ordered pages with 14 visual definitions. Both saved copies were repaired and verified through the live API; both LearnPowerBI copies still have seven pages. Checksums confirmed existing Parquet and DuckDB files were unchanged. The live service now reports version 0.4.0 and parser version 3. Duplicate old Death2PowerBI listeners were replaced with one updated service; exclusive port binding prevents another process from silently sharing its port. Separate import tests with identical filenames verify independent IDs, manifests and DuckDB totals. Report library tests verify switching, saved selection, duplicate filenames and storage fallback. The new dropdown was verified in the served HTML; JavaScript syntax checks passed.

## Source filter translation fix

The report's EmployeeType (groups) = Billable and Division (groups) selections translate into SQL; People filters propagate to Hours through the extracted active relationship. Report and page filters are preserved separately. Tested all 38 compilable queries from LearnPowerBI (35 slicers, 3 charts) against its converted DuckDB database. Category percentage results match an independently written SQL calculation with both source filters applied. Twenty further data visuals still require complex DAX/expression mappings; they show specific limitations. Unknown filter predicates are rejected. Unit coverage includes empty drill-through definitions, NULL, quotes, relationship propagation and combined same-table predicates. JavaScript syntax checks passed. HTTP verified the updated page and repaired manifests are served. Browser reload verification stalled, so visual browser QA is incomplete.

## PBIR page detection fix

Verified against the supplied LearnPowerBI.pbix: seven pages in report order, one hidden Template page, active Introduction page, and 104 visual definitions. The live application API was verified to serve all seven repaired pages. Regression checks cover enhanced PBIR with report.json, standalone PBIR page definitions, and legacy UTF-16 layouts. Hidden page labels are included in the interface. Existing imports are upgraded from their original source archive without reconverting semantic data when loaded by the updated service. Restart the Python service after installing the update.

Passed on October 17, 2026:

- Python compilation and JavaScript syntax checks.
- Synthetic zipped PBIP project with two CSV rows, one report page and one visual: imported and preserved positions/types.
- CSV converted to Parquet and DuckDB through the DuckDB fallback converter (Polars was unavailable in the build environment).
- Verified SQL sum against fixture rows.
- HTTP SQL query endpoint returned the expected total.
- HTTP query endpoint rejected writes and blocked external file reads.
- Export endpoint returned a ZIP archive.

Not verified:

- A real PBIX extraction: PBIXRay dependencies could not be installed due to environment download/file permission failures. The adapter uses the documented PBIXRay API; install requirements and verify against your own PBIX before relying on decoded values.
- Polars conversion path, PBIP cache.abf extraction, large models, actual Power BI visual fidelity and browser visual QA.
- Hosting: source-upload execution was rejected by the environment approval policy, so no deployed application URL is claimed.

The application is an initial local workbench with partial report reconstruction, not full Power BI engine compatibility.


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


## Version 0.13.0: authentication and account isolation

`py test_accounts.py` runs against an isolated temporary account store and HTTP server. It verifies the bootstrap admin, account creation and username uniqueness, current-password checks, password reset/change session revocation, logout/expiry, legacy report ownership, same-filename uploads for two users, server-side isolation for list/query/DAX/export/delete, disabled external file access in SQL, admin-only account actions/shutdown, CSRF and cross-origin checks, private custom visual packages, deletion transfer to admin and protected admin/self-deletion. `py test_lifecycle.py` now authenticates its temporary admin and retains the report deletion/shutdown checks. No production accounts or report data are used by these tests.


## HTML snapshots and imported documents (0.16.0)

Browser checks exported the two-page example, re-imported its downloaded HTML, verified SVG charts/cards/tables and switched pages inside the isolated viewer. An external HTML fixture with embedded data and JavaScript changed regions and values on click; parent-document access and fetch requests were blocked. A real Life in Europe export contained all three pages, preserved 24.20% and 81.77% formatting and had no pending loading markers. Backend tests verify ownership, administrator access, sharing/revocation, separate IDs for duplicate filenames, deletion, snapshot hidden-page metadata and malformed-package rejection. JavaScript tests verify Unicode package round-tripping, standalone scripts, title escaping and the viewer policy. Custom visual live frames are represented by documented placeholders in snapshots.


## Bar/column labels

Six bar/column mappings compile and render SVG with label settings enabled; regression checks cover show/hide, percentage formats, precision, fixed units, grouped offsets, nulls and negative values. All 33 chart mappings and chart-interaction tests pass. Live LearnPowerBI Executive Summary rendered labels 88%, 79%, 73% on its horizontal chart and 88%, 86%, 83% on its column chart. Label settings came from the saved PBIX definitions without re-importing. Native labels are serialized as SVG text in snapshot exports.


## Offline country geocoding

Country-only point-map queries render SVG. Tests cover names, ISO codes, aliases, France's mainland location, ambiguous/unmatched/null values, explicit-coordinate priority, incomplete coordinate errors and original country identities for chart interactions. Browser verification used Life in Europe's Life Satisfaction map without any coordinate fields; its markers rendered and a country selection filtered the neighboring table to the selected country. Two unsupported territories were listed in visible warnings.


## Map navigation

Live Life in Europe checks verified +/−/reset controls, pan buttons and drag panning. Clicking Iceland filtered the table to Iceland (0.10) and retained 200% zoom after the filter refreshed the page. Dragging changed marker positions without changing that selection. Snapshot export restored the map at 200%; the exported Life Satisfaction page contained map SVG with no live controls or loading placeholders. Automated checks exercise live Vega projection signals for all four map type names and confirm reset restores the initial geometry (allowing insignificant floating-point differences in legend layout).


## Bundled Native Style KPI

Verified native Indicator/TrendLine/Goal roles against the supplied package's value/trend/target categorical mapping, optional trend/target inputs, measure formats and calendar ordering for month-name trends. Browser validation rendered LearnPowerBI Executive Summary through the actual package: 86%, Goal 80%, +7.73% variance, success icon and one shaded SVG trend path. Backend tests confirm unauthenticated built-in requests fail, ordinary authenticated users can load the component, and private package isolation is unchanged. Existing five account tests and custom-visual/data-view tests passed.


## Employee report legacy filter compatibility

Identified inactive field-slot metadata as the source of Unsupported legacy filter expression. Regression cases ignore only recognized field descriptors without conditions and continue to reject predicate expressions. Verified the actual imported report retains two active filters on each of its three main pages and none on its tooltip page, with DuckDB confirming eleven 2014 year/month pairs excluding December. Parser v5 converts this report's legacy named selections, table aliases, source sorts and titles to native queryState. Browser validation rendered New Hires charts; its matrix now reaches a separate Python DAX qualified-column limitation. No semantic tables were replaced.


## Employee matrix DAX repair

Resolved unqualified columns via each measure's home table, added SQL execution for eligible aggregates and base-table blank filters, and implemented bounded classic SAMEPERIODLASTYEAR. Against the actual imported model, New Hires / Actives and Separations / Bad Hires matrices completed with 210 / 60 / 210 rows in 9.2 / 6.5 / 8.8 seconds and 9,031 / 15,362 / 9,871 steps respectively. Independent SQL verified thirty populated measure cells across all three pages. Synthetic tests cover nested home tables, 120,001-row facts without Python materialization, preserved captured FILTER contexts under ALL, calendar-filter replacement, leap-month extension and noncontiguous-date rejection. Existing function, change-measure and budget regressions pass.
