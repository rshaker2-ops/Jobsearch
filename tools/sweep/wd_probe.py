import json,sys,urllib.request,concurrent.futures as cf,itertools
UA={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Content-Type":"application/json","Accept":"application/json"}
WDS=["wd1","wd3","wd5","wd10","wd12","wd2"]
SITES=["External","Careers","External_Career_Site","ExternalCareerSite","{T}_Careers",
       "{T}Careers","careers","External_Careers","{T}_External_Career_Site","Search"]
def probe(args):
    ten,wd,site=args
    site=site.replace("{T}",ten.capitalize())
    u=f"https://{ten}.{wd}.myworkdayjobs.com/wday/cxs/{ten}/{site}/jobs"
    body=json.dumps({"appliedFacets":{},"limit":1,"offset":0,"searchText":""}).encode()
    try:
        r=urllib.request.Request(u,data=body,headers=UA,method="POST")
        d=json.loads(urllib.request.urlopen(r,timeout=12).read().decode())
        t=d.get("total",0)
        if t and t>0: return (ten,wd,site,t)
    except Exception: pass
    return None
names=[l.strip() for l in open(sys.argv[1]) if l.strip()]
combos=[(n,w,s) for n in names for w in WDS for s in SITES]
print(f"probing {len(names)} companies x {len(WDS)} pods x {len(SITES)} sites = {len(combos)} combos",file=sys.stderr)
found={}
with cf.ThreadPoolExecutor(max_workers=30) as ex:
    for r in ex.map(probe,combos):
        if r and r[0] not in found: found[r[0]]=r
for ten,(t,w,s,n) in sorted(found.items()):
    print(f"{t}|{w}|{s}|{n}")
print(f"\nLIVE WORKDAY TENANTS: {len(found)}",file=sys.stderr)
