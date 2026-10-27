"""Admin-facing OIDC configuration; secrets are write-only over the API."""
import json
import os
from pathlib import Path
import re
import uuid


class FederationSettings:
    def __init__(self, security):
        self.root=Path(security)
        self.path=self.root/'oidc.json'

    def _read(self):
        return json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {}

    def status(self, origin):
        config=self._read()
        return {'providers':{name:{'enabled':item.get('enabled',bool(item.get('client_id') and item.get('client_secret'))),'clientId':item.get('client_id',''),'tenantId':item.get('tenant_id','') if name=='entra' else '', 'hasSecret':bool(item.get('client_secret')), 'callbackUrl':origin+'/auth/callback/'+name} for name in ('google','entra') for item in [config.get(name,{})]}}

    def save(self, payload, origin):
        name=payload.get('provider')
        if name not in ('google','entra'):
            raise ValueError('Choose Google or Entra ID.')
        enabled=payload.get('enabled')
        if not isinstance(enabled,bool):raise ValueError('Enabled must be true or false.')
        config=self._read();previous=config.get(name,{})
        client=payload.get('clientId','');secret=payload.get('clientSecret','');tenant=payload.get('tenantId','')
        for value,limit in ((client,512),(secret,8192),(tenant,100)):
            if not isinstance(value,str) or len(value)>limit or '\x00' in value:raise ValueError('Invalid federation configuration.')
        client=client.strip();tenant=tenant.strip()
        if client and name=='google' and not re.fullmatch(r'[A-Za-z0-9_.-]+\.apps\.googleusercontent\.com',client):
            raise ValueError('Enter the Google OAuth web application client ID ending in .apps.googleusercontent.com.')
        if client and name=='entra':
            try:client=str(uuid.UUID(client))
            except ValueError:raise ValueError('Enter the Entra application client UUID.') from None
        if tenant and name=='entra':
            try:tenant=str(uuid.UUID(tenant))
            except ValueError:raise ValueError('Entra requires a specific directory tenant UUID.') from None
        changed=client!=previous.get('client_id','')
        saved_secret=secret or (previous.get('client_secret','') if not changed else '')
        if enabled and (not client or not saved_secret or name=='entra' and not tenant):
            raise ValueError('Enabling requires a client ID, client secret, and (for Entra) tenant UUID. A changed client ID requires its matching secret.')
        config[name]={**previous,'enabled':enabled,'client_id':client,'client_secret':saved_secret,**({'tenant_id':tenant} if name=='entra' else {})}
        self.root.mkdir(parents=True,exist_ok=True)
        temporary=self.root/('oidc-'+uuid.uuid4().hex+'.tmp')
        try:
            with temporary.open('x',encoding='utf-8') as file:json.dump(config,file)
            if os.name!='nt':temporary.chmod(0o600)
            os.replace(temporary,self.path)
        finally:temporary.unlink(missing_ok=True)
        return self.status(origin)
