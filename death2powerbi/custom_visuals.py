"""Read PBIVIZ packages as data; executable content runs only in browser sandboxes."""
from pathlib import PurePosixPath
import hashlib
import io
import json
import re
import ipaddress
import zipfile

MAX_PACKAGE = 32 * 1024 * 1024


def normalize(resource, filename):
    if not isinstance(resource, dict):
        raise ValueError('Invalid PBIVIZ resource document')
    visual = resource.get('visual', {})
    if not isinstance(visual, dict):
        raise ValueError('Invalid PBIVIZ visual metadata')
    guid = visual.get('guid', '')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{3,150}', guid):
        raise ValueError('The visual package has no valid visual GUID')
    content = resource.get('content', {})
    if not isinstance(content, dict):
        raise ValueError('Invalid PBIVIZ content')
    if not isinstance(content.get('js'), str) or not content['js'].strip():
        raise ValueError('The visual package contains no JavaScript bundle')
    if resource.get('externalJS'):
        raise ValueError('External JavaScript dependencies are not supported; use a self-contained PBIVIZ bundle')
    capabilities = resource.get('capabilities', {})
    if not isinstance(capabilities, dict):
        raise ValueError('Invalid PBIVIZ capabilities/content')
    if not isinstance(capabilities.get('dataRoles', []), list) or any(not isinstance(role, dict) for role in capabilities.get('dataRoles', [])):
        raise ValueError('Invalid visual data roles')
    if not isinstance(capabilities.get('objects', {}), dict) or any(not isinstance(obj, dict) for obj in capabilities.get('objects', {}).values()):
        raise ValueError('Invalid visual formatting objects')
    unsafe = {'__proto__', 'prototype', 'constructor'}
    if any(role.get('name') in unsafe for role in capabilities.get('dataRoles', [])) or any(name in unsafe for name in capabilities.get('objects', {})):
        raise ValueError('Invalid custom visual role or object name')
    if len(capabilities.get('dataRoles', [])) > 128 or any(name in unsafe for obj in capabilities.get('objects', {}).values() for name in obj.get('properties', {})):
        raise ValueError('Invalid or excessive custom visual properties')
    encoded = json.dumps(resource, sort_keys=True, ensure_ascii=False).encode()
    ident = hashlib.sha256(encoded).hexdigest()[:32]
    networks = []
    for privilege in capabilities.get('privileges', []):
        if privilege.get('name') == 'WebAccess':
            for domain in privilege.get('parameters', []):
                if re.fullmatch(r'https://(?:\*\.)?[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+(?:/)?', domain) and not re.search(r'localhost|127\.0\.0\.|\.local(?:/|$)', domain, re.I):
                    try:
                        ipaddress.ip_address(domain.removeprefix('https://').removeprefix('*.').rstrip('/'))
                        continue
                    except ValueError:
                        pass
                    networks.append(domain.rstrip('/'))
    return {'id': ident, 'filename': filename, 'guid': guid, 'name': visual.get('displayName') or visual.get('name') or guid,
            'version': visual.get('version', ''), 'apiVersion': resource.get('apiVersion', ''),
            'capabilities': capabilities, 'networkDomains': sorted(set(networks)),
            'js': content['js'], 'css': content.get('css') or resource.get('style') or '',
            'stringResources': resource.get('stringResources', {})}


def read_package(filename, content):
    if len(content) > MAX_PACKAGE:
        raise ValueError('PBIVIZ package exceeds 32 MB')
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        infos = archive.infolist()
        if len(infos) > 500 or sum(i.file_size for i in infos) > MAX_PACKAGE:
            raise ValueError('Expanded PBIVIZ package exceeds its limits')
        names = set()
        for item in infos:
            path = PurePosixPath(item.filename.replace('\\', '/'))
            if path.is_absolute() or '..' in path.parts or ':' in item.filename or item.filename in names:
                raise ValueError('Invalid or duplicate PBIVIZ archive path')
            names.add(item.filename)
        package = json.loads(archive.read('package.json'))
        resources = package.get('resources', [])
        preferred = package.get('metadata', {}).get('pbivizjson', {}).get('resourceId')
        resource = next((r for r in resources if r.get('resourceId') == preferred), None)
        if not resource:
            resource = next((r for r in resources if str(r.get('file', '')).endswith('.pbiviz.json')), None)
        if not resource or resource.get('file') not in names:
            raise ValueError('The package visual resource was not found')
        result = normalize(json.loads(archive.read(resource['file'])), filename)
        if package.get('visual', {}).get('guid') != result['guid']:
            raise ValueError('PBIVIZ package and resource GUIDs differ')
        return result


def metadata(package):
    return {k: v for k, v in package.items() if k not in ('js', 'css', 'stringResources')}


def save_package(root, package):
    root.mkdir(exist_ok=True)
    path = root / (package['id'] + '.json')
    if not path.exists():
        temporary = root / (package['id'] + '.tmp')
        temporary.write_text(json.dumps(package), encoding='utf-8')
        temporary.replace(path)
    return metadata(package)


def register_embedded(root, files):
    registered, warnings = [], []
    for name, content in files.items():
        if not name.lower().endswith('.pbiviz.json'):
            continue
        try:
            resource = json.loads(content.decode('utf-8-sig'))
            registered.append(save_package(root, normalize(resource, PurePosixPath(name).name)))
        except (ValueError, TypeError, KeyError) as error:
            warnings.append('Custom visual ' + name + ': ' + str(error))
    return registered, warnings
