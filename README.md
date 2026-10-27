# Death2BI — clean Docker Desktop package

This is the latest base application from this workspace, with Python 3.13 and its complete Linux dependency set specified for an amd64 Docker image. Application version: 0.24.33; report parser: 36. The build context contains only application code, documentation, bundled browser assets and the public, MIT-licensed Walkers visual with its pinned catalog and license. `SOURCE_MANIFEST.json` lists their SHA-256 hashes.

Comparison-report conversion now separates tooltip fields from chart series, supports native Button slicers and target-specific slicer interactions, and preserves constant model format definitions including signed compact currency data labels. The bounded Python evaluator supports same-table TREATAS targets for disconnected selectors. Existing saved report metadata upgrades automatically.

No personal reports, account database, federation configuration/secrets, TLS certificates, branding settings, sharing policies, or uploaded custom visual packages are included. The base application's built-in KPI remains included. Embedded custom visuals can be registered when reports are imported into the new installation.

## Build and add to Docker Desktop

Start Docker Desktop in Linux containers mode. In PowerShell run:

```powershell
& "C:\Users\gdeck\Documents\Codex\2026-10-17\cr\outputs\Death2BI-Docker\Build-and-Install.ps1"
```

The script builds `death2bi:latest` directly into Docker Desktop's `desktop-linux` engine, starts a temporary test container, verifies login and a clean profile, and removes only that temporary container and its anonymous volume. The built image remains visible in **Docker Desktop → Images**. No image is pushed to a registry.

The first build requires Internet access for the official Python base image, Debian runtime libraries and Python packages. All 23 Python dependencies are version- and hash-pinned in `requirements.lock`; compatible Linux CPython 3.13 wheels were verified against PyPI. `DEPENDENCY_WHEELS.json` records wheel hashes. No host Python installation is needed to build or run the image.

## Run the clean application

```powershell
Set-Location "C:\Users\gdeck\Documents\Codex\2026-10-17\cr\outputs\Death2BI-Docker"
docker --context desktop-linux compose up -d
```

Open **http://127.0.0.1:8766**. Port 8766 avoids the existing desktop application on 8765. Publishing is restricted to the host's loopback interface. The server listens on the container's interfaces so Docker forwarding can reach it.

The clean installation creates only the default local account: **admin** / **Death2PowerBI!**. Change its password using the account controls. Google and Entra ID start unconfigured. Reports, accounts and settings created in this installation persist in the new `death2bi-state` Docker volume, separate from the desktop application. Reusing that volume retains its settings; rebuilding the image does not reset it.

The container runs as UID/GID 10001 with a private file-creation mask. `/var/lib/death2bi` stores its state. The image does not mount or read your desktop application's folders. The default compose configuration drops Linux capabilities and disables privilege escalation.

## Stop, start, update and export the image

```powershell
docker --context desktop-linux compose stop
docker --context desktop-linux compose start
# Rebuild and replace the container after updating the build package:
docker --context desktop-linux compose up -d --build
# Optional portable image archive after a successful build:
docker --context desktop-linux save --output Death2BI-image.tar death2bi:latest
```

The application's Restart server action reloads its process inside the container. Shut down server exits the container; `compose start` starts it again. The compose restart policy retries unexpected failures, not a clean shutdown. Do not delete the named volume if you want to retain container-created reports and accounts.

To change the external port, update both the compose port mapping and `D2PBI_BASE_URL` to the same browser origin. Federated callbacks depend on that origin. TLS and federation can be configured later through Administration.

## Verification status

The clean staged application was tested using a separate disposable profile: default admin login succeeds, no saved reports or extra accounts exist, federation has no configured providers, and branding has its defaults. Existing account, federation, restart and RLS regression tests were also run. Linux wheel availability was verified for all pinned dependencies.

**The Docker image build and Docker Desktop installation were not executed in the Codex session:** access to the Docker Desktop named pipe was denied, and sandbox escalation was rejected by the session approval policy. Run the script above from your normal PowerShell session to complete the image build, Linux container smoke test and Docker Desktop installation.

## Pillow dependency update

The image pins Pillow 13.0.0 in requirements.lock, with the compatible Linux Python 3.13 wheel SHA-256 recorded in DEPENDENCY_WHEELS.json. Downloaded wheel bytes were verified against PyPI. Icon decode, resize and PNG output were checked with an isolated Pillow 13.0.0 Windows runtime; a Linux container build was not run here. Rebuild and recreate your container to replace Pillow in an existing installation, then rescan the resulting image. Updating this folder alone does not modify an existing image or container.

## Cryptography dependency update

The Docker image now pins cryptography 50.0.2 and retains Pillow 13.0.0. Compatible Linux Python 3.13 wheel bytes and SHA-256 hashes were verified against PyPI. Existing cffi 2.0.0 satisfies the new release requirements. Application PEM/PFX certificate handling, TLS access checks and RSA SHA256 signing/verification passed with an isolated cryptography 50.0.2 Windows runtime. A Linux image build and vulnerability rescan were not run here. Rebuild the image and recreate the container, then rescan the resulting image; changing this build folder does not update existing containers.

## Bundled packaging-library updates

The Docker lock now includes setuptools 83.0.0, urllib3 2.8.0 and msgpack 1.2.1, with PyPI-verified wheel hashes for Linux Python 3.13. The Docker build checks these installed versions, runs pip check, and then removes pip and ensurepip from the final filesystem. This also removes pip's privately bundled copies of packaging libraries, which are not replaced by installing newer top-level packages. Runtime dependency upgrades must be made by rebuilding the image; pip is intentionally unavailable inside the finished container.

Verified compatible Linux wheel hashes and isolated Windows imports, MessagePack round trips and urllib3 URL parsing. A Linux container build and scanner rescan were not performed here. Rebuild and recreate the container to deploy the update, then scan that new image. Existing images and containers are unchanged.


## Parallel DAX workers (0.23.0)

The clean build context includes the bounded DAX process pool and browser cancellation support. It starts two reusable workers by default (one on a single-CPU host), each using one DuckDB thread. Set `D2BI_DAX_WORKERS`, `D2BI_DAX_THREADS`, `D2BI_DAX_QUEUE_SIZE` or `D2BI_DAX_QUEUE_SECONDS` in Compose environment settings to tune it; the app README documents ranges, limits and diagnostics. SIGTERM and normal shutdown/restart close worker processes. RLS remains isolated per request.

Rebuild the image and recreate its container to deploy this build-context update. The packaged application is version 0.23.0; personal reports, accounts and federation settings are excluded. The existing state volume remains separate. This update does not rebuild or replace an already-running Docker image.

## Sharing domain and public report links (0.24.0)

Administration now separates the public sharing domain/protocol/port from the internal listener. Saving the sharing address updates newly generated invitation and public links immediately. For the default Compose mapping, keep listening port 8765 and sharing port 8766. For an HTTPS reverse proxy, set the sharing domain to its public hostname, HTTPS and sharing port 443; configure routing and DNS separately. Listener/interface changes require restart, and changing an internal container port also requires matching Compose mappings and health checks. Saved settings in the state volume override deployment defaults. Federated callback registration must match the startup address.

Report owners and administrators can create anonymous, read-only public links through Share report. Administrators can inspect all links and revoke them. Link creation explicitly acknowledges access to the report's queryable data; RLS-enabled reports cannot be public. See the application README for expiry, access controls and restrictions. The clean build context contains version 0.24.0 and excludes personal reports, public links, accounts, server-address settings and federation credentials. Rebuild and recreate the container to deploy; no existing Docker image was rebuilt during this update.

## Ranking performance and custom filter visuals (0.24.1)

This clean build includes request-local batched DAX row scoring, floating-point context-filter corrections and the capability-declared custom filter API used by WeightedDualLabelSlider. Existing reports benefit without reimporting; their source measures and data are preserved. The ordinary interpreter remains the fallback for unsupported expressions, and RLS/worker limits are unchanged. See the app README for supported behavior and verification. Rebuild and recreate the container to deploy this updated build context; existing Docker images and containers are not replaced by updating these files.


## Selected-row and scatter conversion fixes (0.24.4)

Includes bounded nested ALLSELECTED table contexts, grouped parameter/cohort aggregates, polar scatter scalar calculations, text scatter X axes, static DateSpan filters, resolved Top N formatting contexts and image-valued native button slicers. Existing models receive these shared runtime fixes without reimporting. Rebuild and recreate the container to deploy this build-context update. Personal reports and settings remain excluded.


## Series-specific chart labels (0.24.5)

Includes shared bar/column support for measure-driven custom labels, independent per-series visibility, fonts and colors, including labels carried by transparent helper series. Existing Top N and optional-formatting query fixes also apply. All three What is our fear.pbix charts were verified without editing source measures. Rebuild and recreate the container to deploy.


## Bar axis bounds and point transparency (0.24.6)

Bar and column charts with a positive maximum and an automatic minimum retain their zero baseline. Explicit minima, logarithmic axes and independent non-bar scales retain their authored behavior. Category- and measure-scoped bar transparency use the shared presentation resolver. Verified the Heights value 4 on the 0–7.5 scale in WeNeverStopFearing.pbix. Rebuild and recreate the container to deploy this update.


## Shared grouped aggregates and crash diagnostics (0.24.7)

Eligible inner `ADDCOLUMNS` group plans are bounded to 64 identities per batch while preserving all rows, order, lineage, secured context and the shared request budget.

Includes bounded reuse of identical numeric aggregate subqueries in grouped DAX plans and sanitized native worker crash diagnostics. Existing execution limits and secured query contexts are preserved. Rebuild and recreate the container to deploy; private reports and settings are excluded.

## Palette neutrals and embedded AVIF artwork (0.24.8)

Includes fixed white/black palette neutral resolution for dark themes and embedded AVIF support across import, saved-report metadata upgrades, image rendering, SVG raster resources and snapshot export. Disabled image backgrounds remain transparent. Rebuild and recreate the container to deploy this update.

## Adaptive categorical x-axis labels (0.24.9)

Shared charts prefer horizontal labels where the resolved font and category spacing permit. Labels can wrap at spaces into two lines before rotation is considered. Width and height expressions adapt to resizing, with bounded rotated label extents to retain plotting space. Explicit angles, hidden axes and numeric/time scales keep their settings. Existing reports and future imports use the same renderer. Rebuild and recreate the container to deploy.
