"""Deterministic spatial sampling of a complete secured scatter query result."""
import math,time
from collections import defaultdict

def sample(rows, columns, types, axes, limit=3500, *, check=None):
    started=time.perf_counter()
    def checked(values):
        if check is None:
            yield from values
            return
        for index,value in enumerate(values):
            if index%4096==0:check()
            yield value
    if check:check()
    x,y,size=(axes.get(k,-1) for k in ('x','y','size'))
    if not all(isinstance(i,int) and -1<=i<len(columns) for i in (x,y,size)) or x<0 or y<0:
        raise ValueError('Scatter sampling requires valid X and Y column indices.')
    def finite(v):
        return v is not None and not isinstance(v,(str,bool)) and math.isfinite(v)
    valid=[r for r in checked(rows) if finite(r[x]) and finite(r[y]) and (size<0 or finite(r[size]) and r[size]>=0)]
    stats={}
    if valid:
        xs=[float(r[x]) for r in checked(valid)];ys=[float(r[y]) for r in checked(valid)]
        xmin,xmax=min(xs),max(xs);ymin,ymax=min(ys),max(ys)
        mx=math.fsum(xs)/len(xs);my=math.fsum(ys)/len(ys)
        xx=math.fsum((a-mx)**2 for a in checked(xs));xy=math.fsum((a-mx)*(b-my) for a,b in checked(zip(xs,ys)))
        stats={'minX':xmin,'maxX':xmax,'minY':ymin,'maxY':ymax,'slope':xy/xx if xx else None,'intercept':my-xy/xx*mx if xx else None}
    occupied=0
    if len(valid)>limit:
        mandatory={0,len(valid)-1,xs.index(xmin),xs.index(xmax),ys.index(ymin),ys.index(ymax)}
        cells=defaultdict(list)
        for i,(a,b) in enumerate(checked(zip(xs,ys))):
            if i in mandatory:continue
            cell=(min(31,int((a-xmin)/(xmax-xmin)*32)) if xmax>xmin else 0,min(31,int((b-ymin)/(ymax-ymin)*32)) if ymax>ymin else 0)
            cells[cell].append(i)
        occupied=len(cells);remaining=limit-len(mandatory);allocation={k:1 for k in cells};remaining-=len(cells)
        capacity=sum(len(v)-1 for v in cells.values())
        fractions=[]
        for k,v in cells.items():
            exact=remaining*(len(v)-1)/capacity if capacity else 0
            allocation[k]+=int(exact);fractions.append((exact-int(exact),k))
        left=limit-len(mandatory)-sum(allocation.values())
        for _,k in sorted(fractions,reverse=True)[:left]:allocation[k]+=1
        chosen=set(mandatory)
        for k,indices in cells.items():
            n=allocation[k]
            for j in range(n):chosen.add(indices[min(len(indices)-1,int((j+.5)*len(indices)/n))])
        output=[valid[i] for i in sorted(chosen)]
    else:output=valid
    if check:check()
    return {'columns':columns,'types':types,'rows':output,'truncated':False,'sampling':{'algorithm':'spatial-density-grid','inputRows':len(rows),'validRows':len(valid),'plottedRows':len(output),'limit':limit,'occupiedCells':occupied,'stats':stats,'elapsedSeconds':round(time.perf_counter()-started,4)}}
