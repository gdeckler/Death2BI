FROM python:3.13-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    D2BI_STATE_DIR=/var/lib/death2bi D2BI_BIND_HOST=0.0.0.0 \
    D2PBI_BASE_URL=http://127.0.0.1:8766
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 death2bi && useradd --uid 10001 --gid 10001 --no-create-home death2bi \
    && mkdir -p /var/lib/death2bi/data /var/lib/death2bi/security /var/lib/death2bi/custom_visuals \
    && chown -R 10001:10001 /var/lib/death2bi
WORKDIR /app
COPY requirements.lock /tmp/requirements.lock
RUN python -m pip install --no-cache-dir --require-hashes --only-binary=:all: -r /tmp/requirements.lock \
    && python -m pip check && rm /tmp/requirements.lock \
    && python -c "from importlib.metadata import version; expected={'setuptools':'83.0.0','urllib3':'2.8.0','msgpack':'1.2.1','cryptography':'50.0.2','pillow':'13.0.0'}; assert all(version(k)==v for k,v in expected.items())" \
    && python -m pip uninstall --yes pip \
    && python -c "import ensurepip, pathlib, shutil; target=pathlib.Path(ensurepip.__file__).parent; assert target.name=='ensurepip' and target.parent==pathlib.Path('/usr/local/lib/python3.13'); shutil.rmtree(target)" \
    && python -c "import importlib.util; assert importlib.util.find_spec('pip') is None; assert importlib.util.find_spec('ensurepip') is None"
COPY app/ /app/
COPY entrypoint.sh /usr/local/bin/death2bi-entrypoint
RUN chmod 755 /usr/local/bin/death2bi-entrypoint \
    && python -c "import server, pbixray, duckdb, polars, pyarrow, cryptography, PIL" \
    && test ! -f /var/lib/death2bi/security/accounts.sqlite3
LABEL org.opencontainers.image.title="Death2BI" \
      org.opencontainers.image.version="0.24.33" \
      org.opencontainers.image.description="Clean Death2BI application; no personal settings or report data"
USER 10001:10001
EXPOSE 8765
VOLUME ["/var/lib/death2bi"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
 CMD python -c "import socket; s=socket.create_connection(('127.0.0.1',8765),timeout=3); s.close()"
ENTRYPOINT ["/usr/local/bin/death2bi-entrypoint"]
