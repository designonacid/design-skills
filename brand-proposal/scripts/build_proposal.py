# Build a client-facing brand proposal from authored JSON and original assets.
import argparse,base64,html,json,mimetypes,re,subprocess
from pathlib import Path
from svg_construction import construction
E=lambda text:html.escape(str(text or ''))
def data(path):
    p=Path(path);return 'data:'+(mimetypes.guess_type(p)[0] or 'application/octet-stream')+';base64,'+base64.b64encode(p.read_bytes()).decode()
def build(cfg,base,out):
    out.mkdir(parents=True,exist_ok=True);assets=out/'assets';assets.mkdir(exist_ok=True)
    def path(p):return Path(p) if Path(p).is_absolute() else base/p
    def img(p,cls='art'):return f'<img class="{cls}" src="{data(path(p))}" alt="">'
    logo_path=path(cfg['logo']);raw=logo_path.read_text()
    def logo(dark=False,cls='brand-logo'):
        text=re.sub(r'#[0-9A-Fa-f]{6}\b|#[0-9A-Fa-f]{3}\b','#FFFFFF',raw) if dark else raw
        return f'<img class="{cls}" src="data:image/svg+xml;base64,{base64.b64encode(text.encode()).decode()}" alt="{E(cfg["brand_name"])}">'
    font=''.join(f'@font-face{{font-family:"{E(f["family"])}";src:url({data(path(f["path"]))});font-weight:{E(f.get("weight",400))};font-display:block}}' for f in cfg['fonts'])
    family=cfg.get('font_family',cfg['fonts'][0]['family']);margin=48;title_size=float(cfg.get('layout',{}).get('title_size',80))
    if not 60<=title_size<=120:raise ValueError('Layout margin/title_size outside supported ranges')
    slides=[];meta=[]
    for i,s in enumerate(cfg['slides'],1):
        typ=s['type'];dark=s.get('dark',False);title=E(s.get('title','')).replace('\n','<br>');body=E(s.get('body',''));note=E(s.get('note',''))
        head=f'<h1 class="title">{title}</h1>'
        items=''.join(f'<div class="item"><h2>{E(a["title"])}</h2><p>{E(a["text"])}</p></div>' for a in s.get('items',[]))
        if typ=='cover':
            content=f'<div class="cover-brand">{E(cfg["brand_name"])}</div><div class="cover-logo">{logo(True)}</div><h1 class="cover-title">{E(cfg["title"])}</h1><p class="cover-sub">{E(cfg.get("subtitle",""))}</p>';dark=True
        elif typ=='statement':content=f'<h1 class="statement">{title}</h1><p class="statement-body">{body}</p>'
        elif typ in ['text','decision']:content=head+f'<p class="intro">{body}</p><div class="items">{items}</div>'
        elif typ=='logo':content=head+f'<div class="logo-reveal">{logo(dark)}</div><p class="logo-body">{body}</p>'
        elif typ=='construction':
            svg,info=construction(logo_path,s.get('guides'));p=assets/'logo-construction.svg';p.write_text(svg);meta.append(info)
            content=head+f'<p class="deck-sub">{body}</p><div class="construction">{img(p)}</div><div class="construction-key"><span><b class="anchor-key"></b> Anchor</span><span><b class="handle-key"></b> Curve handle</span><span><b class="guide-key"></b> Alignment guide</span></div>';note=E(s.get('note',info['disclosure']))
        elif typ=='analysis':content=head+f'<div class="analysis-art">{img(s["image"])}</div><div class="analysis-items">{items}</div>'
        elif typ=='image':content=head+f'<div class="image-art">{img(s["image"])}</div><p class="image-credit">{E(s.get("credit",""))}</p>'
        elif typ=='versions':content=head+f'<div class="versions"><div>{logo()}</div><div class="inverse">{logo(True)}</div></div><p class="logo-body">{body}</p>'
        elif typ=='typography':content=head+f'<div class="type-main">{E(s["headline"]).replace(chr(10),"<br>")}</div><p class="type-sample">{E(s["sample"])}</p><p class="type-body">{body}</p>'
        elif typ=='palette':
            colors=''.join(f'<div style="background:{E(c["hex"])};color:{"#fff" if sum(int(c["hex"][j:j+2],16) for j in (1,3,5))<380 else "#000"}"><h2>{E(c["name"])}</h2><span>{E(c["hex"])}</span></div>' for c in s['colors'])
            content=head+f'<p class="deck-sub">{body}</p><div class="palette">{colors}</div>'
        elif typ=='editorial':
            content=head+f'<div class="web"><header>{logo()}<span>Insights</span><span>Method</span><span>Talent</span></header><div class="web-content">{img(s["image"])}<div><p class="small">Editorial example</p><h2>{E(s["project"])}<br>× {E(s["studio"])}</h2><p>{body}</p></div></div><p class="credit">{E(s["credit"])}</p></div>'
        elif typ=='social':
            content=head+f'<div class="social-example"><div class="social-image">{img(s["image"])}</div><div class="social-label">{logo(True)}<h2>{E(s["project"])}<br>× {E(s["studio"])}</h2></div></div><div class="social-copy"><h2>{E(s["headline"])}</h2><p>{body}</p><p class="credit">{E(s["credit"])}</p></div>'
        else:raise ValueError('Unknown composition '+typ)
        footer=f'<div class="footer"><span>{E(cfg.get("status",cfg["brand_name"]))}</span><span>{E(cfg.get("date",""))} / {i:02d}</span></div>'
        slides.append(f'<div class="wrap"><section class="slide {"dark" if dark else ""}" data-type="{typ}">{content}<p class="note">{note}</p>{footer}</section></div>')
    css=Path(__file__).with_name('proposal.css').read_text().replace('@FONT@',font).replace('@FAMILY@',family).replace('@MARGIN@',str(margin)).replace('@TITLE@',str(title_size))+cfg.get('layout',{}).get('css','')
    name=re.sub('[^a-zA-Z0-9]+','_',cfg['brand_name']).strip('_')+'_Brand_Proposal'
    doc=f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{E(cfg["brand_name"])} brand proposal</title><style>{css}</style></head><body>'+''.join(slides)+'''<script>function fit(){if(matchMedia('print').matches)return;document.documentElement.style.setProperty('--s',Math.min(1,(innerWidth-32)/1920))}addEventListener('resize',fit);fit()</script></body></html>'''
    hp=out/(name+'.html');hp.write_text(doc);(out/'construction-metadata.json').write_text(json.dumps(meta,indent=2));return hp
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('config');a.add_argument('--out',required=True);a.add_argument('--pdf',action='store_true');a.add_argument('--previews',action='store_true');a.add_argument('--node',default='node');a.add_argument('--playwright-module',default='playwright');a.add_argument('--browser',default='');opt=a.parse_args()
    cp=Path(opt.config).resolve();cfg=json.loads(cp.read_text());out=Path(opt.out).resolve();hp=build(cfg,cp.parent,out);print('HTML:',hp)
    if opt.pdf or opt.previews:
        subprocess.run([opt.node,str(Path(__file__).with_name('render.cjs')),str(hp),opt.playwright_module,opt.browser,str(int(opt.pdf)),str(int(opt.previews))],check=True)
        if opt.previews:
            try:
                from PIL import Image,ImageDraw
                files=sorted((out/'previews').glob('slide-*.png'));cols=4;rows=(len(files)+cols-1)//cols;sheet=Image.new('RGB',(cols*488,rows*303),'#ddd');draw=ImageDraw.Draw(sheet)
                for i,p in enumerate(files):
                    im=Image.open(p).convert('RGB');im.thumbnail((480,270));x=(i%cols)*488;y=(i//cols)*303;sheet.paste(im,(x,y));draw.text((x+8,y+278),str(i+1),fill='black')
                sheet.save(out/'previews/contact_sheet.jpg',quality=90)
            except ImportError:print('Pillow unavailable; individual previews were generated.')
