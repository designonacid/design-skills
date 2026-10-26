"""Explain supported SVG geometry without inventing construction history."""
import argparse, html, json, math, re
import xml.etree.ElementTree as ET
from pathlib import Path
NUM=r"[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?"
def numbers(text): return [float(x) for x in re.findall(NUM,text or '')]
def path_geometry(data):
    tok=re.findall(r'[a-zA-Z]|'+NUM,data);i=0;cmd=None;p=(0.,0.);start=p;anchors=[];handles=[];prev=None;last=None
    arity={'M':2,'L':2,'H':1,'V':1,'C':6,'S':4,'Q':4,'T':2}
    while i<len(tok):
        if tok[i].isalpha():cmd=tok[i];i+=1
        if cmd is None:raise ValueError('Path begins without a command')
        up=cmd.upper();relative=cmd.islower()
        if up=='Z':p=start;anchors.append(p);prev='Z';cmd=None;last=None;continue
        if up not in arity:raise ValueError('Unsupported SVG path command '+cmd+'. Convert to cubic paths first.')
        n=arity[up]
        if i+n>len(tok) or any(t.isalpha() for t in tok[i:i+n]):raise ValueError('Malformed path command '+cmd)
        v=list(map(float,tok[i:i+n]));i+=n
        def point(x,y):return (x+p[0],y+p[1]) if relative else (x,y)
        old=p
        if up in ['M','L','T']:
            end=point(*v)
            if up=='T':
                c=(2*p[0]-last[0],2*p[1]-last[1]) if prev in ['Q','T'] and last else p
                handles.extend([(p,c),(end,c)]);last=c
            else:last=None
            p=end
            if up=='M':start=p;cmd='l' if relative else 'L'
        elif up=='H':p=(v[0]+p[0] if relative else v[0],p[1]);last=None
        elif up=='V':p=(p[0],v[0]+p[1] if relative else v[0]);last=None
        elif up=='C':
            c1=point(*v[:2]);c2=point(*v[2:4]);end=point(*v[4:]);handles.extend([(p,c1),(end,c2)]);p=end;last=c2
        elif up=='S':
            c1=(2*p[0]-last[0],2*p[1]-last[1]) if prev in ['C','S'] and last else p
            c2=point(*v[:2]);end=point(*v[2:]);handles.extend([(p,c1),(end,c2)]);p=end;last=c2
        elif up=='Q':
            c=point(*v[:2]);end=point(*v[2:]);handles.extend([(p,c),(end,c)]);p=end;last=c
        anchors.append(p);prev=up
    return anchors,handles

def construction(source,guides=None):
    source=Path(source);root=ET.fromstring(source.read_text());vb=numbers(root.get('viewBox'))
    if len(vb)!=4:raise ValueError('Construction requires an SVG viewBox')
    x,y,w,h=vb;nodes=[];handles=[];converted=[]
    css=''.join(e.text or '' for e in root.iter() if e.tag.split('}')[-1]=='style')
    hidden=set(re.findall(r'\.([\w-]+)\s*\{[^}]*display\s*:\s*none',css))
    def visit(e):
        tag=e.tag.split('}')[-1]
        if tag in ['defs','style','title','desc','metadata']:return
        if 'display:none' in e.get('style','').replace(' ','') or e.get('display')=='none' or hidden.intersection(e.get('class','').split()):return
        if e.get('transform'):raise ValueError('Flatten SVG transforms before constructing the diagram')
        if tag in ['svg','g']:
            for child in e:visit(child)
            return
        if tag=='path':a,b=path_geometry(e.get('d',''));nodes.extend(a);handles.extend(b)
        elif tag in ['circle','ellipse']:
            cx=float(e.get('cx',0));cy=float(e.get('cy',0));rx=float(e.get('r',e.get('rx',0)));ry=float(e.get('r',e.get('ry',0)));k=4*(math.sqrt(2)-1)/3
            pts=[(cx+rx,cy),(cx,cy+ry),(cx-rx,cy),(cx,cy-ry)];nodes.extend(pts)
            for p,cs in zip(pts,[[(cx+rx,cy-k*ry),(cx+rx,cy+k*ry)],[(cx-k*rx,cy+ry),(cx+k*rx,cy+ry)],[(cx-rx,cy-k*ry),(cx-rx,cy+k*ry)],[(cx-k*rx,cy-ry),(cx+k*rx,cy-ry)]]):handles.extend((p,c) for c in cs)
            converted.append(tag)
        elif tag in ['polygon','polyline']:
            a=numbers(e.get('points'));nodes.extend(list(zip(a[::2],a[1::2])))
        elif tag=='rect':
            if float(e.get('rx',0)) or float(e.get('ry',0)):raise ValueError('Convert rounded rectangles to paths first')
            a=float(e.get('x',0));b=float(e.get('y',0));c=float(e.get('width',0));d=float(e.get('height',0));nodes.extend([(a,b),(a+c,b),(a+c,b+d),(a,b+d)])
        elif tag=='line':nodes.extend([(float(e.get('x1',0)),float(e.get('y1',0))),(float(e.get('x2',0)),float(e.get('y2',0)))])
        else:raise ValueError('Unsupported visible SVG element: '+tag)
    visit(root)
    if not nodes:raise ValueError('No visible SVG geometry found')
    nodes=list(dict.fromkeys((round(a,6),round(b,6)) for a,b in nodes))
    pad=max(w*.10,h*.15);stroke='vector-effect="non-scaling-stroke"';guides=guides or {'x':[x,x+w],'y':[y,y+h]}
    lines=[]
    for a in guides.get('x',[]):lines.append(f'<line x1="{a}" y1="{y-pad}" x2="{a}" y2="{y+h+pad}"/>')
    for a in guides.get('y',[]):lines.append(f'<line x1="{x-pad}" y1="{a}" x2="{x+w+pad}" y2="{a}"/>')
    raw=source.read_text();inner=re.search(r'<svg\b[^>]*>(.*)</svg>',raw,re.S).group(1)
    inner=re.sub(r'fill\s*:\s*[^;}]+','fill: #E3E5E6',inner)
    inner=re.sub(r'fill="(?!none)[^"]+"','fill="#E3E5E6"',inner)
    handle_svg=[]
    for (a,b),(c,d) in handles:
        if abs(a-c)+abs(b-d)<.001:continue
        handle_svg.append(f'<line x1="{a}" y1="{b}" x2="{c}" y2="{d}" stroke="#292929" stroke-width=".8" {stroke}/><circle cx="{c}" cy="{d}" r="1.45" fill="#292929"/>')
    markers=''.join(f'<rect x="{a-2.6}" y="{b-2.6}" width="5.2" height="5.2" fill="#43BCE4" stroke="#147C9C" stroke-width=".8" {stroke}/>' for a,b in nodes)
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x-pad} {y-pad} {w+pad*2} {h+pad*2}"><rect x="{x-pad}" y="{y-pad}" width="{w+pad*2}" height="{h+pad*2}" fill="white"/>{inner}<g stroke="#58BBDD" stroke-width=".8" {stroke}>{"".join(lines)}</g>{"".join(handle_svg)}{markers}</svg>'
    return svg,{'anchors':len(nodes),'handle_segments':len(handle_svg),'converted_primitives':converted,'source_viewbox':vb,'disclosure':'Source path nodes and handles. Circle/ellipse handles use a conventional four-node cubic representation; the source outline is unchanged.' if converted else 'Source path nodes and control handles; explanatory guides do not document the historical design process.'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('--out',required=True);a=p.parse_args();svg,meta=construction(a.source);Path(a.out).write_text(svg);print(json.dumps(meta,indent=2))
