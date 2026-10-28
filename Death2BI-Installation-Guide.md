# Death2BI Installation Guide

Applies to application version **0.24.34**. Updated **October 28, 2026**.

This guide covers the standalone Python web application and the clean Docker package. Both provide the same browser interface and report-conversion service.

## 1. Choose an installation method

| Method | Distribution | Required on the host | Default browser address |
|---|---|---|---|
| Standalone web application | `Death2BI.zip` | 64-bit Python 3.13 and its installed dependencies | <http://127.0.0.1:8765> |
| Docker | `Death2BI-Docker.zip` | Docker Desktop in Linux containers mode, or Docker Engine with Compose | <http://127.0.0.1:8766> |

The standalone ZIP does not bundle Python. The Docker ZIP is a **build context**, containing a Dockerfile and application files; build it to create an image containing Python and the required dependencies. The packaged Docker dependency target is **Linux amd64/x86-64**.

Power BI Desktop and Node.js are not required to run Death2BI. Initial dependency installation or image building requires Internet access. Disk and memory needs depend on the reports; allow space for retained originals, Parquet files, DuckDB databases, and backups.

## 2. Install the standalone web application on Windows

### 2.1 Prepare Python and extract the application

Install 64-bit Python **3.13**, including pip and the Windows Python launcher. This is the interpreter version used for the current application and Docker runtime. Consult the [Python virtual-environment documentation](https://docs.python.org/3.13/library/venv.html) for interpreter and environment setup.

Extract `Death2BI.zip` into a permanent folder your account can write to. For example, the resulting application directory could be:

```text
C:\Apps\Death2BI\
    server.py
    requirements.txt
    start.cmd
    dist\
    bundled_visuals\
```

The examples below use `C:\Apps\Death2BI`; replace that path with your extracted application directory. Run commands from the directory containing `server.py`, not its parent.

### 2.2 Install dependencies in a virtual environment

Open PowerShell:

```powershell
Set-Location -LiteralPath 'C:\Apps\Death2BI'
py -3.13 --version
py -3.13 -m venv .venv
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
```

Wait for installation to finish successfully. These commands use the environment's interpreter directly, so PowerShell script activation is unnecessary.

### 2.3 Start the application

```powershell
Set-Location -LiteralPath 'C:\Apps\Death2BI'
& '.\.venv\Scripts\python.exe' server.py
```

Keep the terminal open. Open <http://127.0.0.1:8765> in a browser, or use the configured address printed by the server if it has been changed.

For subsequent launches, run the same start command; dependency installation is needed again only when updating requirements or recreating the environment.

**Alternative launcher:** double-click `start.cmd`. It uses the launcher's default `py` interpreter, installs requirements on every launch, and then starts the server. It does not explicitly select the `.venv` interpreter created above. Use the explicit virtual-environment commands for a consistent installation.

### 2.4 Optional: standalone installation on Linux

With Python 3.13, its venv support, and compatible native dependency wheels available, extract the standalone ZIP and run from the extracted `Death2BI` directory:

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python server.py
```

Use the Docker method below when you want the packaged Linux runtime dependencies. `start.cmd` is Windows-only.

## 3. Install the Docker package

The image runs as UID/GID **10001:10001**. Application code is installed in `/app`; persistent application state is stored in `/var/lib/death2bi`.

### 3.1 Windows: Docker Desktop

Install and start [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/). Use **Linux containers** and ensure your PowerShell session can access its engine. Docker Desktop includes Docker Compose; host Python is unnecessary.

Extract `Death2BI-Docker.zip`. For example:

```text
C:\Apps\Death2BI-Docker\
    Dockerfile
    compose.yaml
    requirements.lock
    entrypoint.sh
    Build-and-Install.ps1
    app\
```

From PowerShell, build the image and start the persistent service:

```powershell
Set-Location -LiteralPath 'C:\Apps\Death2BI-Docker'
docker --context desktop-linux version
docker --context desktop-linux compose up -d --build
docker --context desktop-linux compose ps
docker --context desktop-linux compose logs --tail 100 death2bi
```

Open <http://127.0.0.1:8766>. The first build downloads the Python base image, system libraries, and pinned Python dependencies, so it can take several minutes.

**Optional build and smoke-test helper:** instead of the initial build command, run:

```powershell
& '.\Build-and-Install.ps1'
docker --context desktop-linux compose up -d
```

The helper builds `death2bi:latest` for Linux amd64, tests default sign-in and the clean profile in a temporary container, and removes that temporary container and its temporary volume. It leaves the image in Docker Desktop. The following `compose up` command starts the regular installation. If organizational policy prevents running the PowerShell helper, use the manual Docker commands above.

### 3.2 Linux: Docker Engine

Install [Docker Engine](https://docs.docker.com/engine/install/) and the [Docker Compose plugin](https://docs.docker.com/compose/install/) on an x86-64 Linux host. Your account must have the engine access required by your deployment's Docker configuration.

Extract the Docker ZIP, change into the directory containing `Dockerfile` and `compose.yaml`, and run:

```bash
docker version
docker compose version
docker build --platform linux/amd64 --pull --tag death2bi:latest .
docker compose up -d --no-build
docker compose ps
docker compose logs --tail 100 death2bi
```

The Windows helper's `desktop-linux` context is not required on a Linux Engine installation. Use <http://127.0.0.1:8766> from a browser on that host; see section 6 for access from another computer.

### 3.3 Understand Docker persistence

The supplied Compose configuration publishes **host port 8766** to **container port 8765**, with access restricted to the host's loopback interface. Its logical state volume is `death2bi-state`.

Docker Compose normally prefixes the actual volume name with the project name, for example `death2bi-docker_death2bi-state`. Keep the same Compose project name and installation directory when updating. A different project name can select a different, initially empty volume and make the installation appear to have lost its reports.

Rebuilding an image does not reset the existing state volume. Routine updates must retain it. Do not use `docker compose down -v` or remove the state volume when preserving reports and accounts.

## 4. First sign-in and report import

A **fresh** installation creates one local administrator account:

| Setting | Value |
|---|---|
| Username | `admin` |
| Default password | `Death2PowerBI!` |

Sign in at the appropriate browser address. Click your account name in the top bar to change the password. Existing installations retain their current passwords; updating or rebuilding does not restore the default password.

Administrators can create accounts on **Accounts**, manage memberships on **Groups**, and configure application settings on **Administration**. Accounts start with **My Workspace**. Administrators can use **Reports owned by → All accounts** to see reports belonging to other users.

To verify an installation:

1. Select **Load example** and confirm the browser interface renders.
2. Select a workspace and choose **Import report** to upload a small PBIX.
3. Open **Report pages**, **Semantic model**, and **Compatibility** to inspect the imported report and any unsupported elements.
4. Confirm the report remains available after a normal server restart.

PBIX files are preferred. For PBIP, choose the complete project folder or upload a project ZIP containing its report and semantic-model directories. A `.pbip` file alone is a project pointer. Model data must be available through a supported cache or CSV/Parquet exports. HTML snapshots and supported self-contained HTML reports can also be imported. The upload limit is **1 GB**; report compatibility varies with DAX, visual type, and source data availability.

## 5. Choose where reports and settings are stored

### 5.1 Default locations

| Content | Standalone default | Docker default |
|---|---|---|
| Application code | Extracted `Death2BI` folder | `/app` |
| Application state | Extracted `Death2BI` folder | `/var/lib/death2bi` |
| Reports and converted models | State folder's `data` directory | `/var/lib/death2bi/data` |
| Accounts, sharing, federation, TLS and branding | State folder's `security` directory | `/var/lib/death2bi/security` |
| Installed custom visuals | State folder's `custom_visuals` directory | `/var/lib/death2bi/custom_visuals` |

### 5.2 Configure the complete state directory before first startup

For a new standalone installation, `D2BI_STATE_DIR` can separate application state from application code. Set it before starting the server and use the same setting on every subsequent launch:

```powershell
Set-Location -LiteralPath 'C:\Apps\Death2BI'
$env:D2BI_STATE_DIR = 'D:\Death2BIState'
& '.\.venv\Scripts\python.exe' server.py
```

The selected directory must be available and writable by the server account. PowerShell `$env:` assignments last for the current session and its child processes; retain this assignment in your regular startup script or service configuration. A later double-click of the unmodified `start.cmd` will not read an assignment from a terminal that has been closed.

This environment setting selects a state directory; it does **not** copy an existing installation into it. Pointing it at a different empty directory initializes a separate profile. For existing installations, use the report-storage workflow below when moving report files only.

For Docker, a fresh deployment can replace the named-volume mapping with a bind mount to an existing data-disk folder. On a Linux host, for example:

```yaml
    volumes:
      - /mnt/death2bi:/var/lib/death2bi
```

Prepare that host folder so UID/GID `10001:10001` can read and write it. Apply the Compose change by recreating the container. Replacing a mount does not migrate existing volume contents; back up and copy existing state while stopped before changing an established installation's mount.

### 5.3 Move reports through Administration

Administrators can relocate reports without moving accounts and settings:

1. Open **Administration → Report storage**.
2. Enter a new, empty, absolute folder path on the **server**. Choose a report-only location outside the application files and separate from the current report folder.
3. Select **Validate location**.
4. Confirm copying existing reports while keeping the originals, then select **Save storage location**.
5. Select **Restart server** and confirm. Allow time for copying and verification.
6. Return to **Report storage** and verify the active folder and report count.

The original files are retained. You can cancel the pending change before restart. A failed copy keeps the original location active and reports the error. An unavailable configured active folder stops startup rather than silently opening an empty library. Links/junctions and overlapping or nonempty destinations are rejected.

In Docker, enter a **container path**, such as `/mnt/reports/library`, backed by an already configured persistent mount. Administration cannot attach an Azure disk or expose a host folder to a container. Add the mount first, make it writable by UID/GID 10001, and retain it on future starts.

## 6. Configure addresses, HTTPS and federation

The default listener is suitable for access from the same computer. For other computers, open **Administration → Server domain and port**:

- Set the sharing domain to the hostname or IP address users can actually reach. Enter a hostname without `http://`, a path, or a port.
- Set the sharing protocol and externally visible sharing port.
- Configure the listening port and network interface if direct remote access is required. Restart to apply listener changes.
- Configure the corresponding DNS records, firewall rules, and reverse-proxy routing separately.

The sharing address controls generated report links. Setting a domain in Administration does not create DNS records or network access. A link containing `127.0.0.1` points to the recipient's own computer.

For Docker, retain internal listening port **8765** unless you also adjust the image health check and port mappings. To use host port 9000 locally, change the relevant Compose entries to:

```yaml
    ports:
      - "127.0.0.1:9000:8765"
    environment:
      D2PBI_BASE_URL: http://127.0.0.1:9000
```

Recreate the container after changing Compose. For direct LAN access, publish the intended host network address instead of loopback and use a reachable hostname in the application sharing settings. Saved Administration settings override environment defaults; check those settings when reusing an existing state volume.

Use **Administration → Server HTTPS certificate** to upload a PEM certificate chain and matching private key, or a PFX/P12 bundle. Restart after saving. The certificate must cover the hostname users browse to and be trusted by their browsers. When an external proxy terminates HTTPS, configure the public sharing address to match that HTTPS endpoint.

Use **Administration → Federated sign-in** to configure Google and Microsoft Entra ID. After changing the public origin, restart the server before configuring or testing federation; the sign-in callbacks use the startup origin even though new sharing links use the saved sharing address immediately. Then use the callback URLs displayed on the federation page for provider registration. The page links to provider setup documentation. Create the provider application registrations, enter the required identifiers and secret, and enable the provider. The clean package contains no personal federation credentials. Changing the public origin also requires updating provider callback registrations.

A user's first federated sign-in must start from a valid single-use report invitation. This creates the linked local account stub; subsequent sign-ins can use that linked identity. Enabling a provider does not automatically associate its users with the local administrator account.

## 7. Start, restart and stop

Administrators have **Restart server** and **Shut down server** controls; both require confirmation. Restart applies pending listener, HTTPS and report-storage changes. In-progress queries can be interrupted, and a storage copy can extend restart time.

For standalone installations, start again using the same interpreter, environment settings and application directory. Ctrl+C in the server terminal also stops it. The supplied launcher does not install an operating-system service; configure service supervision separately if you need unattended startup.

For Docker Desktop, run these commands from the Docker package directory:

```powershell
# Stop and later start the existing installation:
docker --context desktop-linux compose stop
docker --context desktop-linux compose start

# Show status or recent logs:
docker --context desktop-linux compose ps -a
docker --context desktop-linux compose logs --tail 100 death2bi
```

On Linux Engine, omit `--context desktop-linux`. The application's **Restart server** reloads its process inside the container. **Shut down server** exits the container cleanly; the supplied `on-failure` restart policy will not restart a clean shutdown. Use `compose start` to start it again.

## 8. Back up, update and restore

### Back up

Stop the application or container before making a consistent filesystem backup. Back up the **entire state directory**, including `security` and `custom_visuals`, plus the active report folder if it was relocated outside that directory. Include hidden files such as `.death2bi-report-storage-owner.json`, Compose configuration, and the details of any external mounts.

For the default standalone installation, this means backing up its runtime directories inside the application folder. For Docker, back up the persistent state volume or bind mount, and every separately mounted report folder. A report download or snapshot is not a backup of accounts, sharing policies, or the complete installation. Protect state backups because they contain authentication settings and other private configuration.

### Update the standalone application

1. Stop the server and back up its state and active report folder.
2. Extract the new ZIP into a separate staging directory.
3. Copy the new application files into the existing installation while preserving its runtime `data`, `security`, and `custom_visuals` directories and any external report folder. Keep the existing installation path.
4. From that installation directory, update dependencies and start:

```powershell
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
& '.\.venv\Scripts\python.exe' server.py
```

Use the same `D2BI_STATE_DIR` setting, if configured. Reload the browser and verify existing accounts and reports. Retain the matching old application and state backup if rollback is needed; newer versions may upgrade stored metadata or account schemas.

### Update Docker

Back up state first. Keep the existing Compose project identity, state volume, custom Compose settings and external mounts. Replace the package's application/build files with the new version, then rebuild and recreate:

```powershell
Set-Location -LiteralPath 'C:\Apps\Death2BI-Docker'
docker --context desktop-linux compose stop
docker --context desktop-linux compose build --pull
docker --context desktop-linux compose up -d --no-build --force-recreate
docker --context desktop-linux compose logs --tail 100 death2bi
```

On Linux Engine, omit the Desktop context. Rebuilding does not modify a running container until it is recreated. The image intentionally omits pip; update dependencies through the image build. Retaining the existing state preserves reports, accounts and settings.

### Restore

With the service stopped, restore the state and report-folder backups together, restore the mounts and file permissions, and start with the same state location and Compose project. Report-storage configuration contains absolute paths: restore those paths/mounts too, or reconcile the configuration before starting. Verify sign-in, sharing and several reports before accepting new uploads. Restoring an older backup replaces newer changes at the restored locations.

## 9. Troubleshooting

| Symptom | What to check |
|---|---|
| `py` or Python 3.13 is not found | Verify the Python installation and launcher. Use the intended interpreter explicitly rather than another installed Python version. |
| Dependency installation fails | Confirm 64-bit Python 3.13, working Internet/proxy access, and a writable environment. Review the first pip error before starting the app. |
| Port conflict or Windows error 10048 | Open the existing instance or stop it normally. Another server cannot use the same address/port; one state directory also has a single-server runtime lease. |
| Docker daemon/context access fails | Start Docker Desktop in Linux containers mode and confirm `docker --context desktop-linux version` succeeds. Linux Engine installations use their own engine context. |
| Docker opens an older application version | Rebuild the image and recreate the container. Plain `compose up -d` can reuse an existing image. |
| Reports appear missing after an update | Check `D2BI_STATE_DIR`, Compose project/volume identity, mounts, current account/workspace/owner filter, and **Administration → Report storage** before importing duplicates. |
| Permission denied on a Docker bind mount | Ensure the host folder and report folders are writable by UID/GID 10001. |
| Startup reports unavailable report storage | Restore the configured disk/mount/path or correct its permissions. Startup deliberately refuses to substitute an empty report library. |
| Default administrator password fails | An existing profile retains its changed password. Use an administrator's password-reset workflow; do not delete the account database to reset one password. |
| Sharing or federated sign-in uses the wrong address | Check the Administration sharing domain/protocol/port, Docker mapping or proxy, and provider callback registrations. |
| Some visuals do not convert | Open **Compatibility** and inspect the visual error. Successful installation does not imply full support for every Power BI/DAX/custom-visual feature. |

## 10. Verify completion

Installation is ready when you can sign in, view the example, import and reopen a report, restart without losing it, and identify the state and active report folders for backup.

These instructions were checked against the version 0.24.34 application, launcher, Dockerfile, Compose file and build helper. A Docker image build was not run as part of preparing this guide; the included helper performs its container smoke test when you run it with working Docker engine access.
