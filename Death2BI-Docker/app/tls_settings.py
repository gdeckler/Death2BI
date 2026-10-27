"""Validated, private, restart-applied HTTPS configuration."""
import base64
import json
import os
from pathlib import Path
import ssl
import uuid
import urllib.parse
from datetime import datetime, timezone
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs12


class TLSSettings:
    def __init__(self, security):
        self.root = Path(security) / 'tls'

    def config(self):
        file = self.root / 'settings.json'
        return json.loads(file.read_text(encoding='utf-8')) if file.exists() else {'enabled': False}

    def status(self):
        c = self.config()
        return {k: c[k] for k in ('enabled', 'origin', 'subject', 'issuer', 'expires', 'fingerprint') if k in c}

    def context(self):
        c = self.config()
        if not c.get('enabled'):
            return None
        ident = c['bundle']
        if not isinstance(ident, str) or len(ident) != 32 or any(x not in '0123456789abcdef' for x in ident):
            raise ValueError('Invalid HTTPS certificate configuration.')
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(self.root / ident / 'certificate.pem', self.root / ident / 'private-key.pem')
        return context

    def _commit(self, value):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o777 if os.name == 'nt' else 0o700)
        temporary = self.root / (uuid.uuid4().hex + '.tmp')
        try:
            temporary.write_text(json.dumps(value), encoding='utf-8')
            if os.name != 'nt': temporary.chmod(0o600)
            os.replace(temporary, self.root / 'settings.json')
        finally:
            temporary.unlink(missing_ok=True)

    def save(self, payload):
        origin = str(payload.get('origin') or 'https://127.0.0.1:8765').rstrip('/')
        u = urllib.parse.urlsplit(origin)
        if u.scheme != 'https' or not u.hostname or u.path or u.query or u.fragment or u.username or u.password or u.port is not None and not 1<=u.port<=65535:
            raise ValueError('Enter an HTTPS origin without a path, credentials or query, using a port from 1 to 65535.')
        def decode(name):
            value = payload.get(name) or ''
            if not isinstance(value, str) or len(value) > 512000:
                raise ValueError('Certificate files must each be smaller than 375 KB.')
            return base64.b64decode(value, validate=True)
        certificate, private_key = decode('certificate'), decode('privateKey')
        password = payload.get('password')
        if password is not None and (not isinstance(password, str) or len(password) > 4096):
            raise ValueError('Invalid private-key password.')
        password = password.encode() if password else None
        try:
            if payload.get('format') == 'pkcs12':
                key, leaf, chain = pkcs12.load_key_and_certificates(certificate, password)
                if not leaf or not key:
                    raise ValueError('The PFX must include a certificate and private key.')
                certs = [leaf, *(chain or [])]
            else:
                certs = x509.load_pem_x509_certificates(certificate)
                key = serialization.load_pem_private_key(private_key, password=password)
                leaf = certs[0]
            now = datetime.now(timezone.utc)
            if not leaf.not_valid_before_utc <= now < leaf.not_valid_after_utc:
                raise ValueError('The certificate is expired or not yet valid.')
            if leaf.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo) != key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo):
                raise ValueError('The certificate and private key do not match.')
        except Exception as error:
            if isinstance(error, ValueError) and str(error) in ('The certificate is expired or not yet valid.', 'The certificate and private key do not match.', 'The PFX must include a certificate and private key.'):
                raise
            raise ValueError('Could not read the certificate/key. Use PEM or PFX/P12 with the correct password.') from None
        ident = uuid.uuid4().hex
        folder = self.root / ident
        folder.mkdir(parents=True, mode=0o777 if os.name == 'nt' else 0o700)
        try:
            (folder / 'certificate.pem').write_bytes(b''.join(c.public_bytes(serialization.Encoding.PEM) for c in certs))
            (folder / 'private-key.pem').write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
            for file in folder.iterdir():
                if os.name != 'nt': file.chmod(0o600)
            value = {'enabled': True, 'bundle': ident, 'origin': origin, 'subject': leaf.subject.rfc4514_string(), 'issuer': leaf.issuer.rfc4514_string(), 'expires': leaf.not_valid_after_utc.isoformat(), 'fingerprint': leaf.fingerprint(hashes.SHA256()).hex()}
            # OpenSSL validates that the saved chain and key can actually serve TLS.
            check = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            check.load_cert_chain(folder / 'certificate.pem', folder / 'private-key.pem')
            self._commit(value)
        except Exception:
            for file in folder.iterdir():
                file.unlink()
            folder.rmdir()
            raise
        return self.status()

    def disable(self):
        self._commit({**self.config(), 'enabled': False})
        return self.status()
