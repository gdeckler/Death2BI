"""Decode embedded Power BI Shape Map geometry without remote resources."""
import copy

def features(document):
    if document.get('type') == 'FeatureCollection':
        result = copy.deepcopy(document.get('features', []))
    elif document.get('type') == 'Topology':
        transform = document.get('transform')
        def arc(index):
            points = document['arcs'][index if index >= 0 else ~index]
            x = y = 0
            result = []
            for point in points:
                if transform:
                    x += point[0]; y += point[1]
                    result.append([x*transform['scale'][0]+transform['translate'][0], y*transform['scale'][1]+transform['translate'][1]])
                else:
                    result.append(list(point))
            return result if index >= 0 else result[::-1]
        def ring(indices):
            points = []
            for index in indices:
                part = arc(index)
                points.extend(part if not points else part[1:])
            return points
        def geometry(g):
            kind = g.get('type')
            if kind == 'Polygon':return {'type':kind,'coordinates':[ring(r) for r in g['arcs']]}
            if kind == 'MultiPolygon':return {'type':kind,'coordinates':[[ring(r) for r in p] for p in g['arcs']]}
            raise ValueError('Shape Map requires polygon geometry')
        result = []
        for obj in document.get('objects', {}).values():
            for g in obj.get('geometries', []) if obj.get('type')=='GeometryCollection' else [obj]:
                result.append({'type':'Feature','id':g.get('id'),'properties':copy.deepcopy(g.get('properties',{})),'geometry':geometry(g)})
    else:
        raise ValueError('Shape Map resource must be TopoJSON or GeoJSON')
    if len(result)>20000:raise ValueError('Shape Map exceeds 20,000 features')
    for f in result:
        if f.get('geometry',{}).get('type') not in ('Polygon','MultiPolygon'):raise ValueError('Shape Map requires polygon geometry')
        props = f.setdefault('properties',{})
        identity = ('name','nameLong','isoA2','isoA3','isoN3','adm0A3','NAME','NAME_LONG','ISO_A2','ISO_A3')
        selected = [props[k] for k in identity if k in props]
        keys = [str(v) for v in selected or props.values() if isinstance(v,(str,int,float))]
        if f.get('id') is not None:keys.append(str(f['id']))
        props['keys'] = keys
        props.setdefault('name', next(iter(keys), 'Unnamed shape'))
    return result
