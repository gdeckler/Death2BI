# Row-level security

Administrators configure native Death2BI row policies in **Administration → Row-level security**. RLS is opt-in per native report, and remains disabled until an administrator saves an enabled policy. Imported Power BI Desktop DAX security roles are not automatically imported or executed. No existing report has been given an arbitrary policy during installation.

## Configure and test

1. Choose a report and add named roles.
2. Assign local accounts and/or local groups. These assignments do not grant report access: share the report separately.
3. Add column rules. Values use JSON, such as `["US","CA"]`, `[2025]`, or `[null]`. Comparisons accept a single JSON value or one-element array. Supported operations are equality/inequality, in/not-in, numeric/date/string comparisons, is blank and is not blank. Combine multiple rules for ranges or multiple columns.
4. A value can instead reference the current account ID, username, or federated email. Missing identity values deny the rule. IDs are the preferred stable ownership reference; emails and usernames can change. Comparisons use DuckDB's column comparison semantics, including case-sensitive string equality.
5. Enable RLS, save, and use **Test saved policy as a user**. Preview requires that user to have report access. It reports effective roles and permitted row counts, with an optional bounded SELECT preview. Administrators preview as unrestricted administrators; choose an ordinary account to test restrictions.

Within each role, rules combine with AND. Assigned roles combine with OR (additive access). Enabling RLS with no applicable role returns no rows from any model table. An unrestricted role must be explicitly marked; assigning one grants all rows. Administrators always bypass RLS. Report owners do not bypass it unless they are administrators.

## Relationship scope

Rules propagate from dimensions to facts through active many-to-one relationships, and through active one-to-one relationships in both directions. Ordinary bidirectional chart-filter settings do not automatically enable bidirectional security. Administrators may explicitly enable bidirectional security on the report. Ambiguous security paths, unsupported active relationship cardinalities, missing columns and policy/model mismatches deny access instead of returning unfiltered data.

Unrelated tables (and tables outside the permitted direction of propagation) remain unrestricted within an assigned role, just as a rule on one table is not a blanket restriction on all disconnected data. Secure sensitive disconnected tables explicitly. This initial implementation does not accept arbitrary SQL or DAX predicates, many-to-many security, or every Tabular security behavior.

## Enforcement

Every SQL, Python DAX and SQL-based CSV request uses the current server-side policy. Restricted requests create an isolated in-memory DuckDB database containing only permitted rows. The original database is never attached to that query connection, and external access and automatic extension loading are disabled. Querying `main.Table`, changing ordinary DAX filters with ALL/REMOVEFILTERS, and changing visual filters cannot restore original hidden rows. Initial security materialization has a 30-second limit; failure denies access. Request-specific copies add CPU/memory overhead, especially with large models. Query/DAX/export budgets still apply after security materialization.

Model metadata exposes filtered row counts, category domains and parameter rows to restricted users. Raw model/Parquet/database ZIP exports are blocked for those users because they would contain unfiltered data. Filtered CSV and viewer snapshots remain available. A CSV assembled from client-supplied rows contains only the data the client supplied; the server does not reconstruct that data from hidden rows.

Live RLS cannot sanitize pre-existing HTML, snapshot data, images or static text. HTML/snapshot imports cannot enable these policies; replacing a protected native report with HTML does not make its embedded document available to restricted users. Exported viewer snapshots contain already displayed values and are static copies: subsequent policy changes cannot revoke copies already downloaded. RLS is a server access boundary, not protection against someone with direct access to the original model files or administrator credentials.

## Policy lifetime and caching

Policies and account/group assignments are stored in the private accounts SQLite database, separately from report files, and are excluded from distribution ZIPs and report exports. Overwriting an existing report preserves policies; incompatible replacement schemas fail closed until an administrator corrects the rules. Deleting a report removes its active policy. New reports start without a policy. Policy saves record the administrator, timestamp and revision.

The browser rechecks report access and security context on page navigation and before visual data-cache access. Cache keys include account/policy context, model version, schema, relationship topology and source database timestamp. Changed context invalidates prior visual results and refreshes metadata. Requests include an expected security stamp, and the server rejects a changed stamp before opening the query database; the client retries once with a fresh context. Group membership and role assignment changes affect subsequent requests. Already displayed/downloaded data cannot be retroactively withdrawn, and local sorting operates on the already loaded rows.

## Validation

`py -m unittest test_rls` checks dimension-to-fact propagation, additive roles, group membership changes, dynamic identities, missing identities, denied/unassigned users, admin bypass, DAX ALL, schema-qualified SQL, external-file access, literal injection, ambiguity/schema failures, filtered CSV, metadata counts, source-export blocking, security stamps, preview and admin/CSRF enforcement. Account, sharing, federation and server-action regression suites also run against disposable fixtures.
