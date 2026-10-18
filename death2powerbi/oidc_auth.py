"""OIDC authorization-code flow with browser-bound state, PKCE and signed ID tokens."""
import base64
import hashlib
import hmac
import json
import math
import uuid
import os
import re
import secrets
import time
import urllib.parse
import urllib.request
from pathlib import Path


def b64(value):
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode()


def unb64(value):
    return base64.urlsafe_b64decode(value+'='*(-len(value)%4))


def base_url():
    value=os.environ.get('D2PBI_BASE_URL','http://127.0.0.1:8765').rstrip('/')
    url=urllib.parse.urlsplit(value)
    if url.username or url.password or url.query or url.fragment or url.path or not url.hostname or (url.scheme!='https' and not (url.scheme=='http' and url.hostname in ('127.0.0.1','localhost'))):
        raise ValueError('D2PBI_BASE_URL must be an HTTPS origin or an HTTP loopback origin.')
    return value


class OIDC:
    def __init__(self, store, root):
        self.store,self.root=store,root
        self.cache={}

    def configs(self):
        path=self.root/'security'/'oidc.json'
        config=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        result={}
        for name in ('google','entra'):
            item=config.get(name,{})
            if not item.get('client_id') or not item.get('client_secret'):
                continue
            if name=='google':
                issuer='https://accounts.google.com'
                discovery=issuer+'/.well-known/openid-configuration'
            else:
                tenant=item.get('tenant_id','')
                if not re.fullmatch(r'[a-fA-F0-9-]{36}',tenant):
                    raise ValueError('Entra requires a specific tenant UUID.')
                tenant=str(uuid.UUID(tenant))
                issuer='https://login.microsoftonline.com/'+tenant+'/v2.0'
                discovery=issuer+'/.well-known/openid-configuration'
            result[name]={**item,'issuer':issuer,'discovery':discovery}
        return result

    @staticmethod
    def fetch(url, data=None):
        if not url.startswith('https://'):
            raise ValueError('OIDC endpoints must use HTTPS.')
        req=urllib.request.Request(url,data=urllib.parse.urlencode(data).encode() if data else None,headers={'Accept':'application/json'})
        with urllib.request.urlopen(req,timeout=15) as response:
            if not response.url.startswith('https://'):
                raise ValueError('Insecure identity-provider redirect.')
            content=response.read(1024*1024+1)
        if len(content)>1024*1024:
            raise ValueError('Identity-provider response is too large.')
        return json.loads(content)

    def metadata(self, name):
        config=self.configs().get(name)
        if not config:
            raise ValueError('This identity provider has not been configured.')
        key=config['discovery']
        cached=self.cache.get(key)
        if not cached or cached[0]<time.time():
            metadata=self.fetch(key)
            if metadata['issuer']!=config['issuer']:
                raise ValueError('Identity-provider issuer mismatch.')
            self.cache[key]=(time.time()+3600,metadata)
        return config,self.cache[key][1]

    def start(self, name, invitation=None):
        from invitations import token_hash
        config,meta=self.metadata(name)
        digest=None
        if invitation:
            self.store.preview_invitation(invitation)
            digest=token_hash(invitation)
        state,browser,nonce,verifier=[secrets.token_urlsafe(32) for _ in range(4)]
        with self.store.connect() as db:
            db.execute('DELETE FROM oidc_flows WHERE expires_at<=?',(time.time(),))
            db.execute('INSERT INTO oidc_flows VALUES (?,?,?,?,?,?,?)',(hashlib.sha256(state.encode()).hexdigest(),hashlib.sha256(browser.encode()).hexdigest(),name,nonce,verifier,digest,time.time()+600))
        query={'client_id':config['client_id'],'redirect_uri':base_url()+'/auth/callback/'+name,'response_type':'code','scope':'openid profile email','state':state,'nonce':nonce,'code_challenge':b64(hashlib.sha256(verifier.encode()).digest()),'code_challenge_method':'S256','prompt':'select_account'}
        return meta['authorization_endpoint']+'?'+urllib.parse.urlencode(query),browser

    def validate(self, token, config, meta, nonce):
        from cryptography.hazmat.primitives.asymmetric import rsa,padding
        from cryptography.hazmat.primitives import hashes
        try:
            if not isinstance(token,str) or len(token)>65536:
                raise ValueError()
            header_part,claims_part,signature=token.split('.')
            header=json.loads(unb64(header_part));claims=json.loads(unb64(claims_part))
            if header.get('alg')!='RS256' or header.get('crit'):
                raise ValueError()
            keys=self.fetch(meta['jwks_uri'])['keys']
            matches=[k for k in keys if k.get('kid')==header.get('kid') and k.get('kty')=='RSA' and k.get('use','sig')=='sig' and k.get('alg','RS256')=='RS256']
            if len(matches)!=1:
                raise ValueError()
            key=matches[0];public=rsa.RSAPublicNumbers(int.from_bytes(unb64(key['e']),'big'),int.from_bytes(unb64(key['n']),'big')).public_key()
            public.verify(unb64(signature),(header_part+'.'+claims_part).encode(),padding.PKCS1v15(),hashes.SHA256())
            now=time.time();aud=claims['aud'];aud=[aud] if isinstance(aud,str) else aud
            if config['issuer']=='https://accounts.google.com' and claims.get('iss')=='accounts.google.com':
                claims['iss']=config['issuer']
            if claims['iss']!=config['issuer'] or config['client_id'] not in aud or (len(aud)>1 and claims.get('azp')!=config['client_id']) or claims.get('azp',config['client_id'])!=config['client_id']:
                raise ValueError()
            if any(not isinstance(claims.get(key), (int,float)) or isinstance(claims.get(key),bool) or not math.isfinite(claims[key]) for key in ('exp','iat')):
                raise ValueError()
            if not isinstance(claims['sub'],str) or not claims['sub'] or not hmac.compare_digest(claims['nonce'],nonce) or float(claims['exp'])<=now or float(claims['iat'])>now+60 or float(claims.get('nbf',0))>now+60:
                raise ValueError()
            return claims
        except Exception:
            raise ValueError('The identity provider returned an invalid ID token.') from None

    def callback(self, name, state, browser, code):
        if not state or not browser or not code or len(state)>256 or len(browser)>256 or len(code)>8192:
            raise ValueError('Invalid sign-in callback. Start sign-in again.')
        digest=hashlib.sha256(state.encode()).hexdigest()
        with self.store.lock,self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM oidc_flows WHERE state_hash=?',(digest,)).fetchone()
            if row is None or row['provider']!=name or row['expires_at']<=time.time() or not hmac.compare_digest(row['browser_hash'],hashlib.sha256(browser.encode()).hexdigest()):
                raise ValueError('Sign-in state expired or did not match this browser.')
            db.execute('DELETE FROM oidc_flows WHERE state_hash=?',(digest,))
            flow=dict(row)
        config,meta=self.metadata(name)
        response=self.fetch(meta['token_endpoint'],{'grant_type':'authorization_code','client_id':config['client_id'],'client_secret':config['client_secret'],'code':code,'redirect_uri':base_url()+'/auth/callback/'+name,'code_verifier':flow['verifier']})
        claims=self.validate(response.get('id_token'),config,meta,flow['nonce'])
        return self.store.federated_login(name,claims,flow['invitation_hash'])
