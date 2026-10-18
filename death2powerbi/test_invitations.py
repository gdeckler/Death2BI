"""Invitation races, access control, and locally signed OIDC protocol fixtures."""
import hashlib
import json
import threading
import time
import unittest
import urllib.parse
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric import rsa,padding
from cryptography.hazmat.primitives import hashes
from test_accounts import AccountTests,Client
from accounts import Accounts
from invitations import token_hash
from oidc_auth import OIDC,b64
import server


class Invitations(unittest.TestCase):
    setUp=AccountTests.setUp
    tearDown=AccountTests.tearDown
    create_user=AccountTests.create_user

    def create_link(self,client,report):
        status,result=client.request('POST','/api/reports/'+report+'/invitations',{'hours':24})
        self.assertEqual(status,201)
        return result,urllib.parse.parse_qs(urllib.parse.urlsplit(result['url']).fragment)['invite'][0]

    def test_http_invitation_lifecycle(self):
        alice,a=self.create_user('alice');bob,b=self.create_user('bob')
        report=a.upload(42)[1]['id'];link,raw=self.create_link(a,report)
        self.assertNotIn(raw,json.dumps(self.admin.request('GET','/api/admin/invitations')[1]))
        anonymous=Client(self.httpd)
        for _ in range(2):self.assertEqual(anonymous.request('POST','/api/auth/invite-preview',{'token':raw},csrf=False)[0],200)
        self.assertEqual(b.request('POST','/api/reports/'+report+'/invitations',{})[0],404)
        self.assertEqual(b.request('GET','/api/admin/invitations')[0],403)
        self.assertEqual(b.request('POST','/api/invitations/redeem',{'token':raw},csrf=False)[0],403)
        self.assertEqual(b.request('POST','/api/invitations/redeem',{'token':raw})[0],200)
        self.assertEqual(b.request('POST','/api/invitations/redeem',{'token':raw})[0],400)
        self.assertEqual(b.request('POST','/api/query',{'id':report,'sql':'SELECT * FROM Samples'})[1]['rows'],[[42]])
        audit=self.admin.request('GET','/api/admin/invitations')[1][0]
        self.assertEqual(audit['used_by'],bob['id']);self.assertIsNotNone(audit['used_at'])
        self.assertEqual(b.request('POST','/api/invitations/remove',{'id':link['id']})[0],404)
        self.assertEqual(self.admin.request('POST','/api/invitations/remove',{'id':link['id']})[0],200)
        self.assertTrue(self.store.can_read_report(report,bob))
        unused,token=self.create_link(a,report)
        self.assertEqual(a.request('POST','/api/invitations/remove',{'id':unused['id']})[0],200)
        self.assertEqual(b.request('POST','/api/invitations/redeem',{'token':token})[0],400)
        expired,token=self.create_link(a,report)
        with self.store.connect() as db:db.execute('UPDATE invitations SET expires_at=0 WHERE id=?',(expired['id'],))
        self.assertEqual(b.request('POST','/api/invitations/redeem',{'token':token})[0],400)
        pending,token=self.create_link(a,report)
        self.assertEqual(a.request('POST','/api/delete',{'id':report,'confirmName':'Same.zip'})[0],200)
        self.assertEqual(b.request('POST','/api/invitations/redeem',{'token':token})[0],400)

    def test_atomic_redemption_across_store_instances(self):
        alice,a=self.create_user('alice');bob,b=self.create_user('bob')
        report=self.admin.upload(1)[1]['id'];link,raw=self.create_link(self.admin,report)
        stores=[Accounts(self.store.path),Accounts(self.store.path)]
        barrier=threading.Barrier(2);outcomes=[]
        def redeem(store,user):
            barrier.wait()
            try:store.redeem_invitation(raw,user);outcomes.append('claimed')
            except ValueError:outcomes.append('denied')
        workers=[threading.Thread(target=redeem,args=(stores[0],alice)),threading.Thread(target=redeem,args=(stores[1],bob))]
        for worker in workers:worker.start()
        for worker in workers:worker.join(5)
        self.assertEqual(sorted(outcomes),['claimed','denied'])

    def test_signed_oidc_flow_and_stub(self):
        report=self.admin.upload(1)[1]['id'];link,raw=self.create_link(self.admin,report)
        oidc=OIDC(self.store,self.temp)
        private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        numbers=private.public_key().public_numbers()
        integer=lambda n:b64(n.to_bytes((n.bit_length()+7)//8,'big'))
        jwks={'keys':[{'kty':'RSA','kid':'test','e':integer(numbers.e),'n':integer(numbers.n),'alg':'RS256'}]}
        for provider in ('google','entra'):
            issuer='https://accounts.google.com' if provider=='google' else 'https://login.microsoftonline.com/00000000-0000-0000-0000-000000000001/v2.0'
            config={'client_id':'sample-client','client_secret':'secret','issuer':issuer}
            meta={'authorization_endpoint':issuer+'/authorize','token_endpoint':issuer+'/token','jwks_uri':issuer+'/keys'}
            def sign(claims):
                message=b64(json.dumps({'alg':'RS256','kid':'test'}).encode())+'.'+b64(json.dumps(claims).encode())
                return message+'.'+b64(private.sign(message.encode(),padding.PKCS1v15(),hashes.SHA256()))
            with patch.object(oidc,'metadata',return_value=(config,meta)):
                url,browser=oidc.start(provider,raw);params=urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
                claims={'iss':issuer,'sub':'immutable-id','aud':'sample-client','nonce':params['nonce'][0],'iat':time.time(),'exp':time.time()+300,'email':'admin@example.com','name':'Example'}
                token=sign(claims)
                def fetch(url,data=None):
                    if url==meta['jwks_uri']:return jwks
                    self.assertEqual(data['code'],'code');self.assertEqual(data['client_secret'],'secret')
                    self.assertEqual(b64(hashlib.sha256(data['code_verifier'].encode()).digest()),params['code_challenge'][0])
                    return {'id_token':token}
                with patch.object(oidc,'fetch',side_effect=fetch):
                    with self.assertRaisesRegex(ValueError,'browser'):oidc.callback(provider,params['state'][0],'wrong-browser','code')
                    session,accepted=oidc.callback(provider,params['state'][0],browser,'code')
                    self.assertEqual(accepted,report)
                    user=self.store.session(session)['user'];self.assertFalse(user['isAdmin']);self.assertEqual(user['identity']['provider'],provider)
                    self.assertTrue(self.store.can_read_report(report,user))
                    self.assertNotEqual(user['id'],self.admin_user['id'])
                    with self.assertRaises(ValueError):oidc.callback(provider,params['state'][0],browser,'code')
                    # Test signed claim failures as well as invalid signatures.
                    for change in ({'nonce':'wrong'},{'aud':'other'},{'iss':'https://evil.invalid'},{'exp':0},{'iat':time.time()+1000}):
                        with self.assertRaisesRegex(ValueError,'invalid ID'):oidc.validate(sign({**claims,**change}),config,meta,claims['nonce'])
                    with self.assertRaises(ValueError):oidc.validate(token[:-10]+'bad',config,meta,claims['nonce'])
                client=Client(self.httpd)
                self.assertEqual(client.login(user['username'],'ExamplePassword!1')[0],401)
                with self.assertRaises(ValueError):self.store.reset_password(self.admin_user,user['id'],'NewPassword!1')
                # Returning federation uses the same stub without another invitation.
                returned,_=self.store.federated_login(provider,claims)
                self.assertEqual(self.store.session(returned)['user']['id'],user['id'])
                with self.assertRaises(ValueError):self.store.federated_login(provider,{**claims,'sub':'unknown'})
            link,raw=self.create_link(self.admin,report)


if __name__=='__main__':unittest.main()
