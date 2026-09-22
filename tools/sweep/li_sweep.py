import re,html,json,sys,time,urllib.parse,urllib.request
UA={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept":"text/html,application/xhtml+xml","Accept-Language":"en-US,en;q=0.9"}
BASE="https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DELAY=1.6           # polite; LinkedIn 429s fast if you push

def get(url, tries=3):
    for i in range(tries):
        try:
            r=urllib.request.Request(url,headers=UA)
            return urllib.request.urlopen(r,timeout=25).read().decode("utf-8","replace")
        except Exception as e:
            code=getattr(e,"code",None)
            if code in (429,999): time.sleep(8*(i+1))
            elif i==tries-1: return None
            else: time.sleep(3)
    return None

def txt(pat,c):
    m=re.search(pat,c,re.S)
    return html.unescape(re.sub(r"\s+"," ",m.group(1)).strip()) if m else ""

def search(keywords, location, tpr="r2592000", remote=False, pages=4):
    out=[]
    for p in range(pages):
        q={"keywords":keywords,"location":location,"f_TPR":tpr,"start":p*10}
        if remote: q["f_WT"]="2"
        raw=get(BASE+"?"+urllib.parse.urlencode(q))
        time.sleep(DELAY)
        if not raw: break
        cards=raw.split("<li>")[1:]
        if not cards: break
        for c in cards:
            t=txt(r'class="base-search-card__title"[^>]*>(.*?)</h3>',c)
            if not t: continue
            out.append(dict(
                title=t,
                company=txt(r'class="hidden-nested-link"[^>]*>(.*?)</a>',c) or txt(r'base-search-card__subtitle"[^>]*>\s*<a[^>]*>(.*?)</a>',c),
                loc=txt(r'job-search-card__location"[^>]*>(.*?)</span>',c),
                posted=txt(r'datetime="([^"]+)"',c),
                url=txt(r'href="(https://www\.linkedin\.com/jobs/view/[^"?]+)',c),
                query=keywords))
        if len(cards)<10: break
    return out

MONEY=re.compile(r"\$\s?(\d{3},\d{3}|\d{2,3}(?:\.\d)?[kK])")
def detail(url):
    raw=get(url); time.sleep(DELAY)
    if not raw: return None,[]
    m=re.search(r'show-more-less-html__markup(.*?)</div>',raw,re.S)
    desc=""
    if m:
        d=re.sub(r"<li>","\n- ",m.group(1)); d=re.sub(r"</(p|div|ul|li)>","\n",d)
        desc=html.unescape(re.sub(r"<[^>]+>"," ",d))
        desc=re.sub(r"[ \t]{2,}"," ",re.sub(r"\n{3,}","\n\n",desc)).strip()
    vals=[]
    for mm in MONEY.finditer(raw):
        v=mm.group(1).replace(",","")
        v=float(v[:-1])*1000 if v.lower().endswith("k") else float(v)
        if 60000<=v<=1500000: vals.append(int(v))
    return desc, sorted(set(vals))

if __name__=="__main__":
    spec=json.load(open(sys.argv[1]))
    allrows=[]
    for s in spec["searches"]:
        rows=search(s["keywords"], s.get("location","United States"),
                    s.get("tpr","r2592000"), s.get("remote",False), s.get("pages",4))
        print(f"  [{s['keywords'][:42]:42s}] {s.get('location','US'):18s} -> {len(rows):3d}",file=sys.stderr)
        allrows.extend(rows)
    seen={}; 
    for r in allrows:
        key=(r["title"].lower(), r["company"].lower())
        if key not in seen: seen[key]=r
    rows=list(seen.values())
    json.dump(rows,open(sys.argv[2],"w"),indent=1)
    print(f"TOTAL raw={len(allrows)}  unique={len(rows)}",file=sys.stderr)
