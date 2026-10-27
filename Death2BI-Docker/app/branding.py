"""Validated global application branding, separate from report content."""
import base64
import io
import json
import os
import re
import uuid
from PIL import Image

DEFAULTS = {'name':'Death2BI','slogan':'DIE BI DIE','sidebarColor':'#153e35','icon':'','allowExternalImages':False}

class Branding:
    def __init__(self, directory):
        self.directory=directory
        self.path=directory/'branding.json'
    def load(self):
        if not self.path.exists(): return dict(DEFAULTS)
        return {**DEFAULTS,**json.loads(self.path.read_text(encoding='utf-8'))}
    def save(self, payload):
        if not isinstance(payload,dict): raise ValueError('Invalid branding settings.')
        if payload.get('reset') is True: result=dict(DEFAULTS)
        else:
            result={}
            for key,limit in [('name',80),('slogan',160)]:
                value=payload.get(key)
                if not isinstance(value,str) or len(value.strip())>limit or (key=='name' and not value.strip()) or any(ord(c)<32 for c in value):
                    raise ValueError('Invalid application '+key+'.')
                result[key]=value.strip()
            color=payload.get('sidebarColor','')
            if not isinstance(color,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',color): raise ValueError('Choose a valid background color.')
            result['sidebarColor']=color
            icon=payload.get('icon','')
            if not isinstance(icon,str) or len(icon)>700000: raise ValueError('Icon must be at most 500 KB.')
            result['allowExternalImages']=payload.get('allowExternalImages',self.load().get('allowExternalImages',False))
            if not isinstance(result['allowExternalImages'],bool): raise ValueError('Invalid external image setting.')
            result['icon']=''
            if icon:
                try:
                    raw=base64.b64decode(icon.split(',',1)[1],validate=True)
                    if len(raw)>500000: raise ValueError()
                    with Image.open(io.BytesIO(raw)) as image:
                        if image.format not in ('PNG','JPEG','ICO','WEBP') or max(image.size)>4096: raise ValueError()
                        image.thumbnail((256,256))
                        output=io.BytesIO();image.convert('RGBA').save(output,format='PNG')
                        result['icon']='data:image/png;base64,'+base64.b64encode(output.getvalue()).decode('ascii')
                except Exception: raise ValueError('Choose a valid PNG, JPEG, WebP or ICO image, up to 500 KB and 4096 pixels.') from None
        self.directory.mkdir(parents=True,exist_ok=True)
        temporary=self.directory/('branding-'+uuid.uuid4().hex+'.tmp')
        try:
            temporary.write_text(json.dumps(result),encoding='utf-8');os.replace(temporary,self.path)
        finally: temporary.unlink(missing_ok=True)
        return result
