# Death2PowerBI

A local Power BI migration workbench with account-based access, private report libraries, and an administrator account.

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


## Python DAX calculation budgets

Each visual now has a shared **30-second** Python evaluation budget (previously 8 seconds) and a **1,000,000-step** budget. Calculation-limit messages distinguish time from steps and show elapsed seconds, evaluation steps, the measure/field and group being evaluated. Successful `/api/dax` responses include an `evaluation` diagnostic object. Resource-limit failures show **Calculation limit reached**, rather than Needs mapping.

Server environment variables `D2PBI_DAX_SECONDS` (positive, at most 300) and `D2PBI_DAX_STEPS` (positive integer, at most 100,000,000) override these defaults. Set them before launching the server. The DuckDB interrupt for `/api/dax` follows the Python budget plus two seconds; ordinary `/api/query` keeps its 10-second interrupt. The time budget is cooperative: checks occur during interpretation and after each group, with DuckDB interruption as an additional backstop. Group, field and row limits are unchanged.

LearnPowerBI Executive Summary was tested with saved page/report filters. The bar, column and utilization-card queries passed concurrently in 7.6–8.4 seconds, about 357,000 steps each. The unrendered KPI query hit the original eight-second time budget and completed at roughly 21 seconds with the new budget. This does not add KPI rendering support. Additional interactive filter selections and machine load can change these timings. Regression checks: `py test_dax_budget.py`, `py test_dax.py`, `py test_dax_reference.py`.


## Bar and column data labels

Bar and column charts now read the imported visual's default `labels`/`dataLabels` settings. Explicit show/hide settings, model number formats, label decimal precision, fixed display units, literal colors, font size/family and inside/outside placement for clustered bars/columns are supported. Stacked labels use segment centers; 100% stacked charts display segment percentages. Null labels are omitted and negative labels follow their bars. Theme-based colors fall back to the application label color; per-series/conditional overrides and exact Power BI collision/layout behavior are not yet reproduced. The SVG text is preserved automatically in new snapshot exports; previously exported snapshots remain unchanged. Run `node test_vega.js` for rendering checks.


## Offline country locations in maps

Point maps (`map`/`pointMap`) can now use a Country/Location field without numeric coordinates. A complete explicit latitude/longitude pair takes priority. Otherwise the renderer matches country names, ISO alpha-2/alpha-3 codes and common aliases (such as UK and Türkiye) against the bundled Natural Earth geography. It derives a representative location inside the largest country polygon; these are approximate country locations, not street addresses or capitals. No external geocoding requests or API keys are needed. Country can also be chosen under Chart fields. Existing size/color mappings and cross-filtering retain the original country value.

Unknown, blank and ambiguous names are omitted with visible warnings; bare Congo and Korea require a more specific name or ISO code. Countries/territories absent from the bundled boundary dataset cannot be resolved. In the supplied Life in Europe report, Gibraltar and Svalbard and Jan Mayen are flagged as unmatched. Coordinate pairs with invalid ranges or incomplete mappings still report explicit errors instead of silently using different locations. The existing filled-map matcher shares the country aliases. New snapshot exports preserve rendered maps as SVG.

Checks: `node test_advanced.js`, `node test_vega.js`, `node test_interactions.js`.


## Map navigation

Point and filled maps now include **+**, **−**, **Reset**, directional pan buttons and a zoom percentage. Zoom ranges from 100% to 3200%. Drag the map to pan; a drag does not select a country. When the map has keyboard focus, use +/− to zoom, arrows to pan and Home to reset. Normal marker/country clicks continue to cross-filter other visuals. Reset affects the viewport, not report filters.

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
