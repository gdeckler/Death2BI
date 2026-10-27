"""Validated, restart-applied listener and canonical public address."""
import ipaddress
import json
import os
from pathlib import Path
import re
import urllib.parse
import uuid


def domain(value):
    if not isinstance(value,str) or not value or value!=value.strip() or any(c in value for c in '/\\@?#%\x00\r\n'):raise ValueError('Enter a hostname or IP address without a scheme, path or port.')
    bracketed='[' in value or ']' in value
    if bracketed and not (value.startswith('[') and value.endswith(']')):raise ValueError('Enter a valid IP address.')
    value=value[1:-1] if bracketed else value
    value=value.rstrip('.')
    try:return str(ipaddress.ip_address(value))
    except ValueError:pass
    if bracketed:raise ValueError('Enter a valid IP address.')
    try:value=value.encode('idna').decode('ascii').lower()
    except UnicodeError:raise ValueError('Enter a valid domain name.') from None
    if len(value)>253 or not all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',label) for label in value.split('.')):raise ValueError('Enter a valid domain name.')
    return value


def origin(host,port,scheme):
    host='['+host+']' if ':' in host else host
    return scheme+'://'+host+(':'+str(port) if port!={'http':80,'https':443}[scheme] else '')


_ENV=object()
class ServerAddress:
    def __init__(self,security,inherited_origin=_ENV):
        self.root=Path(security);self.path=self.root/'server-address.json'
        self.inherited_origin=os.environ.get('D2PBI_BASE_URL') if inherited_origin is _ENV else inherited_origin

    def config(self):
        if self.path.exists():return json.loads(self.path.read_text(encoding='utf-8'))
        from tls_settings import TLSSettings
        tls=TLSSettings(self.root).config()
        previous=urllib.parse.urlsplit((tls.get('origin') if tls.get('enabled') else None) or self.inherited_origin or 'http://127.0.0.1:8765')
        port=int(os.environ.get('D2BI_PORT','8765'));public_port=previous.port or (443 if previous.scheme=='https' else 80)
        return {'domain':previous.hostname or '127.0.0.1','port':port,'scheme':previous.scheme,
                'publicPort':public_port if public_port!=port else None,'bindAddress':os.environ.get('D2BI_BIND_HOST','127.0.0.1')}

    def pending_origin(self,https=None):
        from tls_settings import TLSSettings
        tls=TLSSettings(self.root).config()
        enabled=tls.get('enabled',False) if https is None else https
        if not self.path.exists() and https is None:
            legacy=(tls.get('origin') if enabled else None) or self.inherited_origin
            if legacy:return legacy.rstrip('/')
        c=self.config();return origin(c['domain'],c.get('publicPort') or c['port'],'https' if enabled else c.get('scheme','http'))

    def save(self,payload):
        host=domain(payload.get('domain'))
        port=payload.get('port');bind=payload.get('bindAddress','127.0.0.1')
        if isinstance(port,bool) or not isinstance(port,int) or not 1<=port<=65535:raise ValueError('Port must be a whole number from 1 to 65535.')
        if bind not in ('127.0.0.1','0.0.0.0','::1','::'):raise ValueError('Choose a valid listen address.')
        scheme=payload.get('scheme',self.config().get('scheme','http'));public_port=payload.get('publicPort')
        if scheme not in ('http','https'):raise ValueError('Choose HTTP or HTTPS for sharing links.')
        if public_port is not None and (isinstance(public_port,bool) or not isinstance(public_port,int) or not 1<=public_port<=65535):raise ValueError('Sharing-link port must be blank or a whole number from 1 to 65535.')
        value={'domain':host,'port':port,'bindAddress':bind,'scheme':scheme,'publicPort':public_port}
        self.root.mkdir(parents=True,exist_ok=True)
        temp=self.root/('server-address-'+uuid.uuid4().hex+'.tmp')
        try:
            temp.write_text(json.dumps(value),encoding='utf-8')
            if os.name!='nt':temp.chmod(0o600)
            os.replace(temp,self.path)
        finally:temp.unlink(missing_ok=True)
        return {**value,'pendingOrigin':self.pending_origin()}


def authorities(server,active_origin):
    port=server.server_port
    values={urllib.parse.urlsplit(active_origin).netloc}
    for host in ('127.0.0.1','localhost','[::1]'):
        values.add(host+':'+str(port))
        if port in (80,443):values.add(host)
    active=urllib.parse.urlsplit(active_origin)
    if active.hostname in ('localhost','127.0.0.1','::1'):
        active_port=active.port or (443 if active.scheme=='https' else 80)
        values.update(host+':'+str(active_port) for host in ('localhost','127.0.0.1','[::1]'))
    return values
