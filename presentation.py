"""Report presentation metadata, theme resources and role-aware page definitions."""
import base64
import copy
import json
import re
import xml.etree.ElementTree as ET
from pathlib import PurePosixPath


def safe_svg(data):
    """Keep embedded report artwork inert and self-contained when used as an image."""
    if re.search(br'<!DOCTYPE|<!ENTITY', data, re.I):
        return None
    try:
        svg = ET.fromstring(data)
    except ET.ParseError:
        return None
    if svg.tag != '{http://www.w3.org/2000/svg}svg':
        return None
    blocked = {'script', 'foreignobject', 'iframe', 'object', 'embed',
               'animate', 'animatetransform', 'animatemotion', 'set', 'a'}
    for parent in svg.iter():
        for child in list(parent):
            if child.tag.rsplit('}',1)[-1].lower()=='style':
                css=child.text or ''
                targets=re.findall(r'url\s*\((.*?)\)',css,re.I|re.S)
                allowed=lambda target: bool(re.fullmatch(r'#[\w:.-]+|data:font/(?:woff2?|ttf|otf);base64,[a-zA-Z0-9+/=\s]+',target.strip().strip(chr(34)+chr(39))))
                rules=re.findall(r'@([\w-]+)',css)
                unsafe=bool(re.search(r'\\|expression|behavior\s*:|-moz-binding',css,re.I)) or any(rule.lower() not in ('font-face','keyframes','-webkit-keyframes','media','supports') for rule in rules) or any(not allowed(target) for target in targets)
                if unsafe:parent.remove(child)
                continue
            if child.tag.rsplit('}', 1)[-1].lower() in blocked:
                parent.remove(child)
        for key, value in list(parent.attrib.items()):
            name = key.rsplit('}', 1)[-1].lower()
            remove = name.startswith('on') or name == 'base'
            if name == 'href':
                remove |= not (value.startswith('#') or re.fullmatch(r'data:image/(?:png|jpeg|gif|webp|avif);base64,[a-zA-Z0-9+/=\s]+', value))
            if name == 'style':
                # Presentation attributes remain; imported CSS never loads resources.
                remove |= bool(re.search(r'@|expression|\\|url\(\s*["\']?(?!#)', value, re.I))
            if 'url(' in value.lower():
                remove |= any(not re.fullmatch(r'\s*["\']?#[\w:.-]+["\']?\s*', target)
                              for target in re.findall(r'url\((.*?)\)', value, re.I))
            if remove:
                del parent.attrib[key]
    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
    return ET.tostring(svg, encoding='utf-8')


def separate_navigation_icons(page, gap=2.0):
    """Trim small, overlapping navigation slots without reflowing the report."""
    def properties(definition, name):
        result = {}
        for source in (definition.get('objects', {}), definition.get('visualContainerObjects', {})):
            for entry in source.get(name, []):
                if not entry.get('selector') or entry['selector'].get('id') == 'default':
                    result.update(entry.get('properties', {}))
        return result

    def literal(value):
        if not isinstance(value, dict):
            return value
        raw = value.get('expr', value).get('Literal', {}).get('Value')
        return raw.strip("'") if isinstance(raw, str) else raw

    slots = []
    for visual in page.get('visuals', []):
        if visual.get('hidden') or visual.get('type') not in ('image', 'actionButton', 'shape'):
            continue
        bounds = visual.get('navigationSourceBounds') or {key: visual.get(key, 0) for key in ('x', 'y', 'width', 'height')}
        if not (8 <= bounds['width'] <= 64 and 8 <= bounds['height'] <= 64):
            continue
        if bounds['x'] > page.get('width', 1280) * .25 or bounds['y'] > page.get('height', 720) * .15:
            continue
        definition = visual.get('definition', {})
        link = properties(definition, 'visualLink')
        action = str(literal(link.get('type')) or '').lower()
        alt = str(literal(properties(definition, 'general').get('altText')) or '').lower()
        if action not in ('pagenavigation', 'back') and not (visual['type'] == 'image' and alt.startswith(('navigate to ', 'back to '))):
            continue
        text = properties(definition, 'text')
        if literal(text.get('show')) not in (False, 'false') and literal(text.get('text')):
            continue
        visual['navigationIcon'] = True
        rect = [bounds['x'], bounds['y'], bounds['x'] + bounds['width'], bounds['y'] + bounds['height']]
        slots.append((visual, bounds, rect, list(rect)))
    for index, (_, _, a, trimmed_a) in enumerate(slots):
        for _, _, b, trimmed_b in slots[index + 1:]:
            overlap_x = min(a[2], b[2]) - max(a[0], b[0])
            overlap_y = min(a[3], b[3]) - max(a[1], b[1])
            if overlap_x <= -gap or overlap_y <= -gap:
                continue
            dx = (b[0] + b[2] - a[0] - a[2]) / 2
            dy = (b[1] + b[3] - a[1] - a[3]) / 2
            # Near-identical centers usually represent intentional stacked states.
            if abs(dx) < min(a[2] - a[0], b[2] - b[0]) * .25 and abs(dy) < min(a[3] - a[1], b[3] - b[1]) * .25:
                continue
            horizontal = abs(dx) / (a[2] - a[0] + b[2] - b[0]) > abs(dy) / (a[3] - a[1] + b[3] - b[1])
            axis = 0 if horizontal else 1
            left, right = (a, b) if (dx if horizontal else dy) >= 0 else (b, a)
            left_trim, right_trim = (trimmed_a, trimmed_b) if left is a else (trimmed_b, trimmed_a)
            boundary = (left[axis + 2] + right[axis]) / 2
            if boundary - gap / 2 - left_trim[axis] < 8 or right_trim[axis + 2] - boundary - gap / 2 < 8:
                continue
            left_trim[axis + 2] = min(left_trim[axis + 2], boundary - gap / 2)
            right_trim[axis] = max(right_trim[axis], boundary + gap / 2)
    for visual, original, rect, trimmed in slots:
        if rect != trimmed:
            visual['navigationSourceBounds'] = dict(original)
            visual.update(x=trimmed[0], y=trimmed[1], width=trimmed[2] - trimmed[0], height=trimmed[3] - trimmed[1])


def document(value):
    if isinstance(value,dict):return value
    if isinstance(value,bytes):value=value.decode('utf-16') if value.startswith((b'\xff\xfe',b'\xfe\xff')) else value.decode('utf-16-le') if value[:200].count(b'\x00')>20 else value.decode('utf-8-sig')
    try:return json.loads(value or '{}')
    except (ValueError,TypeError):return {}


def merge(left,right):
    result=copy.deepcopy(left)
    for key,value in right.items():
        result[key]=merge(result.get(key,{}) if isinstance(result.get(key),dict) else {},value) if isinstance(value,dict) else copy.deepcopy(value)
    return result


def _tooltip_literal(value):
    """Read authored scalar settings without evaluating conditional expressions."""
    if isinstance(value,dict):
        expression=value.get('expr')
        literal=expression.get('Literal') if isinstance(expression,dict) else None
        if not isinstance(literal,dict):return None
        value=literal.get('Value')
    if isinstance(value,str):
        value=value.strip()
        if value.startswith("'") and value.endswith("'"):
            value=value[1:-1].replace("''", "'")
    return value


def classify_tooltip_pages(model):
    """Retain legacy canvas-tooltip assignments even without a named page type.

    Some PBIX layouts store the target's page type as an undocumented number.
    An enabled Canvas assignment is sufficient evidence; that number alone is
    not. Only assignments reachable from visible pages or known tooltip pages
    may expose hidden tooltip definitions to ordinary report readers.
    """
    pages=model.get('pages',[])
    byid={p['id']:p for p in pages}
    for page in pages:
        binding=page.get('pageBinding')
        explicit=str(page.get('pageType','')).casefold()=='tooltip' or isinstance(binding,dict) and str(binding.get('type','')).casefold()=='tooltip'
        if explicit:
            page['isTooltip']=True
            page.pop('tooltipClassification',None)
        elif page.get('tooltipClassification')=='visualAssignment':
            page['isTooltip']=False
            page.pop('tooltipClassification',None)
    pending=[p for p in pages if not p.get('hidden') or p.get('isTooltip')]
    visited=set()
    while pending:
        page=pending.pop()
        if page['id'] in visited:continue
        visited.add(page['id'])
        for visual in page.get('visuals',[]):
            definition=visual.get('definition',{})
            if not isinstance(definition,dict):continue
            containers=[definition.get(key,{}) for key in ('visualContainerObjects','vcObjects')]
            for container in containers:
                if not isinstance(container,dict):continue
                entries=container.get('visualTooltip',[])
                if not isinstance(entries,list):continue
                for entry in entries:
                    if not isinstance(entry,dict):continue
                    props=entry.get('properties',{})
                    if not isinstance(props,dict):continue
                    show=_tooltip_literal(props.get('show',True))
                    if show is not True and not (isinstance(show,str) and show.casefold()=='true'):continue
                    kind=_tooltip_literal(props.get('type'))
                    section=_tooltip_literal(props.get('section'))
                    if not isinstance(kind,str) or kind.casefold()!='canvas' or not isinstance(section,str):continue
                    target=byid.get(section)
                    if target is None:continue
                    if not target.get('isTooltip'):
                        target['isTooltip']=True
                        target['tooltipClassification']='visualAssignment'
                    pending.append(target)
    return model


def visual_hidden(source):
    """Normalize PBIR visibility and the legacy selection-pane display state."""
    explicit = source.get('isHidden')
    if isinstance(explicit, bool):
        return explicit
    group = source.get('visualGroup')
    if not isinstance(group, dict):
        group = source.get('singleVisualGroup')
    if isinstance(group, dict) and isinstance(group.get('isHidden'), bool):
        return group['isHidden']
    visual = source.get('visual')
    display = visual.get('display') if isinstance(visual, dict) else None
    return isinstance(display, dict) and display.get('mode') == 'hidden'


def enrich_report(result, files, data_dir=None):
    files={k.replace('\\','/'):v for k,v in files.items()}
    docs={k:document(v) for k,v in files.items() if k.lower().endswith(('.json','.pbip','.pbir')) or k.lower()=='report/layout'}
    report=next((d for k,d in docs.items() if k.lower().endswith('report/layout') and d.get('sections')),None)
    if report is None:report=next((d for k,d in docs.items() if k.lower().endswith('/report.json') or k.lower()=='report.json'),{})
    config=document(report.get('config'))
    collection=report.get('themeCollection') or config.get('themeCollection',{})
    themes={};inherited_structural=[]
    for kind in ('baseTheme','customTheme'):
        name=collection.get(kind,{}).get('name','')
        candidates=[d for k,d in docs.items() if PurePosixPath(k).name in (name,name+'.json')]
        if candidates:
            custom=candidates[0]
            if kind=='customTheme':inherited_structural=[k for k in themes if k not in custom and isinstance(themes[k],str) and themes[k].startswith('#')]
            themes=merge(themes,custom)
    if not themes:
        candidates=[d for k,d in docs.items() if 'basethemes/' in k.lower()]
        if candidates:themes=candidates[0]
    from report_schema import audit_documents, normalize_definition
    result['schemaCompatibility']=audit_documents(docs)
    result['theme']={**themes,'_inheritedStructuralColors':inherited_structural}
    result['formattingProvenance']={'themePolicy':'base then custom; authored values preserved','fallbacks':[]}
    result['reportSettings']={**report.get('settings',{})}
    result['reportSettings'].setdefault('locale',report.get('culture') or report.get('locale') or config.get('locale') or 'en-US')
    result['reportObjects']=report.get('objects',config.get('objects',{}))
    assets={};total=0
    for name,data in files.items():
        suffix=PurePosixPath(name).suffix.lower()
        mime={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.gif':'image/gif','.webp':'image/webp','.avif':'image/avif','.bmp':'image/bmp','.svg':'image/svg+xml'}.get(suffix)
        if not mime or len(data)>8*1024**2 or total+len(data)>32*1024**2:continue
        if 'staticresources/' not in name.lower() and 'registeredresources/' not in name.lower():continue
        if suffix == '.svg':
            data = safe_svg(data)
            if data is None:continue
        value='data:'+mime+';base64,'+base64.b64encode(data).decode('ascii')
        assets[name]=value;assets.setdefault(PurePosixPath(name).name,value);total+=len(data)
    result['assets']=assets
    legacy={p.get('name'):p for p in report.get('sections',[])}
    for page in result.get('pages',[]):
        raw=next((d for k,d in docs.items() if k.endswith('/page.json') and d.get('name')==page['id']),legacy.get(page['id'],{}))
        cfg=document(raw.get('config'))
        page['objects']=raw.get('objects',cfg.get('objects',{}))
        page['pageType']=raw.get('type',cfg.get('type',''))
        page['pageBinding']=raw.get('pageBinding',cfg.get('pageBinding',{}))
        page['isTooltip']=str(page['pageType']).lower()=='tooltip' or str(page['pageBinding'].get('type','')).lower()=='tooltip' or any('tooltip' in k.lower() for k in page['objects']) or any(str(e.get('properties',{}).get('tooltip',{}).get('expr',{}).get('Literal',{}).get('Value','')).lower()=='true' for e in page['objects'].get('pageInformation',[]))
        page.pop('tooltipClassification',None)
        visuals={}
        for k,d in docs.items():
            if k.endswith('/visual.json') and '/'+page['id']+'/' in k:visuals[d.get('name')]=d
        if not visuals:
            for v in raw.get('visualContainers',[]):
                c=document(v.get('config'));visuals[c.get('name')]={**v,**c,'position':v,'visual':c.get('singleVisual',{}),'visualGroup':c.get('singleVisualGroup')}
        for v in page.get('visuals',[]):
            source=visuals.get(v['id'],{});pos=source.get('position',{})
            v['z']=pos.get('z',source.get('z',0));v['tabOrder']=pos.get('tabOrder',0)
            v['parentGroup']=source.get('parentGroupName') or source.get('parentGroup')
            v['ownHidden']=visual_hidden(source);v['hidden']=v['ownHidden']
            if v['type']=='azureMap':
                filled=source.get('visual',{}).get('objects',{}).get('filledMap',[])
                v['originalType']='azureMap'
                bubble=source.get('visual',{}).get('objects',{}).get('bubbleLayer',[])
                enabled=lambda entries:any(e.get('properties',{}).get('show',{}).get('expr',{}).get('Literal',{}).get('Value')=='true' for e in entries)
                v['type']='map' if enabled(bubble) else 'filledMap' if enabled(filled) else 'map'
            definition=normalize_definition(v.get('definition',{}),legacy=bool(legacy));v['definition']=definition
            if v['type']=='shapeMap':
                shape=definition.get('objects',{}).get('shape',[])
                resource=next((e.get('properties',{}).get('map',{}).get('geoJson',{}).get('content',{}).get('expr',{}).get('ResourcePackageItem',{}).get('ItemName') for e in shape),None)
                geography=next((d for k,d in docs.items() if resource and PurePosixPath(k).name==resource),None)
                if geography:
                    try:
                        from shape_maps import features
                        v['mapFeatures']=features(geography)
                        v['originalType']='shapeMap';v['type']='filledMap'
                    except (ValueError,KeyError,TypeError) as exc:
                        result.setdefault('warnings',[]).append('Shape Map geometry could not be decoded: '+str(exc))
            if v['type'] in ('advancedSlicerVisual','listSlicer'):
                v['originalType']=v['type']
                v['type']='slicer'
                state=definition.get('query',{}).get('queryState',{})
                if 'Values' in state:
                    definition['query']['queryState']={'Values':state['Values'],**{k:x for k,x in state.items() if k!='Values'}}
            if 'vcObjects' in definition and 'visualContainerObjects' not in definition:definition['visualContainerObjects']=definition['vcObjects']
            if source.get('visualGroup'):
                v['type']='group';v['definition']={'visualType':'group',**source['visualGroup']}
            v['sourcePosition']={k:pos.get(k,v.get(k,0)) for k in ('x','y','width','height')}
        byid={v['id']:v for v in page.get('visuals',[])}
        for v in page.get('visuals',[]):
            parent=v.get('parentGroup');seen={v['id']};chain=[]
            while parent in byid and parent not in seen:
                seen.add(parent);g=byid[parent];chain.insert(0,g);parent=g.get('parentGroup')
            v['groupChain']=[g['id'] for g in chain]
            v['layerPath']=[g.get('z',0) for g in chain]+[v.get('z',0)]
            v['x']=v['sourcePosition']['x']+sum(g['sourcePosition']['x'] for g in chain)
            v['y']=v['sourcePosition']['y']+sum(g['sourcePosition']['y'] for g in chain)
            v['hidden']=v['hidden'] or any(g.get('hidden') for g in chain)
        page['visuals'].sort(key=lambda v:v['layerPath'])
        for index,v in enumerate(page['visuals']):v['layerOrder']=index
        separate_navigation_icons(page)
    classify_tooltip_pages(result)
    bookmarks,groups=bookmark_metadata(docs,config)
    result['bookmarkGroups']=groups
    # Some PBIX saves replace a group ID but retain its old bookmark ID.
    # Reconcile only a unique orphan with a unique untracked live group, and
    # only when every descendant is present in that bookmark's display snapshot.
    for bookmark in bookmarks:
        for page in result.get('pages',[]):
            section=bookmark.get('explorationState',{}).get('sections',{}).get(page['id'],{})
            groups=section.get('visualContainerGroups',{})
            live={v['id'] for v in page.get('visuals',[]) if v['type']=='group'}
            orphans=set(groups)-live;missing=live-set(groups)
            if len(orphans)==len(missing)==1:
                old=next(iter(orphans));new=next(iter(missing))
                descendants=[v['id'] for v in page['visuals'] if new in v.get('groupChain',[])]
                if descendants and all(id in section.get('visualContainers',{}) for id in descendants):
                    groups[new]=groups.pop(old)
                    section.setdefault('repairedGroupIds',{})[old]=new
    result['bookmarks']=bookmarks
    return enrich_data(result,data_dir)


def enrich_data(result,data_dir):
    """Rebuild data-dependent presentation caches without replacing report styles."""
    if data_dir is not None and (data_dir/'model.duckdb').exists():
        import duckdb
        domains={};parameters={};con=duckdb.connect(str(data_dir/'model.duckdb'),read_only=True,config={'enable_external_access':'false','memory_limit':'512MB','threads':'2'})
        try:
            for page in result.get('pages',[]):
                for visual in page.get('visuals',[]):
                    for role,state in visual.get('definition',{}).get('query',{}).get('queryState',{}).items():
                        for parameter in state.get('fieldParameters',[]):
                            col=parameter.get('parameterExpr',{}).get('Column',{});table=col.get('Expression',{}).get('SourceRef',{}).get('Entity');column=col.get('Property')
                            if table and column and table not in parameters:
                                quote=lambda name:'"'+name.replace('"','""')+'"'
                                try:
                                    cursor=con.execute('SELECT * FROM '+quote(table)+' LIMIT 257');names=[d[0] for d in cursor.description];rows=cursor.fetchall()
                                    if len(rows)<=256:
                                        candidates=[name for i,name in enumerate(names) if rows and all(isinstance(r[i],str) and re.fullmatch(r"(?:'(?:[^']|'')+'|[^\[]+)\[[^\]]+(?:\]\][^\]]*)*\]",r[i]) for r in rows)]
                                        actual=column if column in candidates else candidates[0] if len(candidates)==1 else column
                                        parameters[table]={'columns':names,'rows':rows,'fieldColumn':actual}
                                except duckdb.Error:pass
                        if role not in ('Category','Series','Legend','Columns','Location'):continue
                        for projection in state.get('projections',[])[:1]:
                            f=projection.get('field',{});col=f.get('Column') or f.get('GroupRef') or {};table=col.get('Expression',{}).get('SourceRef',{}).get('Entity');column=col.get('Property')
                            if not table or not column or len(domains)>=128:continue
                            key=table+'\x00'+column
                            if key in domains:continue
                            quote=lambda name:'"'+name.replace('"','""')+'"'
                            try:domains[key]=[row[0] for row in con.execute('SELECT DISTINCT '+quote(column)+' FROM '+quote(table)+' ORDER BY 1 LIMIT 1001').fetchall()]
                            except duckdb.Error:continue
        finally:con.close()
        result['colorDomains']=domains
        result['fieldParameters']=parameters
    return result


def bookmark_metadata(docs,config):
    """Retain PBIR ordering/groups and legacy nested bookmark definitions."""
    definitions={d['name']:d for k,d in docs.items() if k.endswith('.bookmark.json') and d.get('name')}
    legacy=config.get('bookmarks',[])
    metadata=next((d.get('items',[]) for k,d in docs.items() if k.lower().endswith('/bookmarks/bookmarks.json')),None)
    ordered=[];groups=[];seen=set()
    def visit(item,ancestors=()):
        if isinstance(item,str):item={'name':item}
        if not isinstance(item,dict) or not item.get('name'):return
        name=item['name']
        if name in ancestors:return
        children=item.get('children')
        if isinstance(children,list):
            group={k:copy.deepcopy(v) for k,v in item.items() if k!='children'}
            group['children']=[c if isinstance(c,str) else c.get('name') for c in children if isinstance(c,(str,dict))]
            if not any(g['name']==name for g in groups):groups.append(group)
            for child in children:visit(child,(*ancestors,name))
        else:
            bookmark=definitions.get(name,item)
            if bookmark.get('explorationState') is not None and name not in seen:
                seen.add(name);ordered.append(bookmark)
    for item in metadata if isinstance(metadata,list) else legacy if isinstance(legacy,list) else []:visit(item)
    for item in legacy if isinstance(legacy,list) else []:visit(item)
    for item in definitions.values():visit(item)
    return ordered,groups


def visible_model(model,actor):
    # Upgrade already imported manifests from their retained visual definitions.
    classify_tooltip_pages(model)
    if actor['isAdmin']:return model
    result=copy.deepcopy(model)
    # Hidden tooltip pages remain renderable on hover, but never enter navigation.
    result['tooltipPages']=[p for p in result.get('pages',[]) if p.get('hidden') and p.get('isTooltip')]
    result['pages']=[p for p in result.get('pages',[]) if not p.get('hidden')]
    allowed={p['id'] for p in result['pages']}
    result['bookmarks']=[b for b in result.get('bookmarks',[]) if b.get('explorationState',{}).get('activeSection') in allowed]
    for b in result['bookmarks']:
        state=b.get('explorationState',{});state['sections']={k:v for k,v in state.get('sections',{}).items() if k in allowed}
    # Do not ship embedded images referenced exclusively by hidden pages.
    names=set()
    def walk(value):
        if isinstance(value,dict):
            ref=value.get('ResourcePackageItem')
            if isinstance(ref,dict):names.add(ref.get('ItemName'))
            for item in value.values():walk(item)
        elif isinstance(value,list):
            for item in value:walk(item)
    walk(result['pages']);walk(result.get('tooltipPages',[]));walk(result.get('theme',{}));walk(result.get('reportObjects',{}))
    result['assets']={k:v for k,v in result.get('assets',{}).items() if PurePosixPath(k).name in names}
    result['hiddenPagesRestricted']=len(result['pages'])!=len(model.get('pages',[]))
    return result
