import json,sys,urllib.request,concurrent.futures as cf,time
UA={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Content-Type":"application/json","Accept":"application/json"}
def search(ten,wd,site,q,limit=20):
    u=f"https://{ten}.{wd}.myworkdayjobs.com/wday/cxs/{ten}/{site}/jobs"
    out=[]
    for off in (0,20):
        body=json.dumps({"appliedFacets":{},"limit":limit,"offset":off,"searchText":q}).encode()
        try:
            r=urllib.request.Request(u,data=body,headers=UA,method="POST")
            d=json.loads(urllib.request.urlopen(r,timeout=20).read().decode())
        except Exception: break
        posts=d.get("jobPostings",[])
        for p in posts:
            out.append(dict(ats="workday",company=ten,title=(p.get("title") or "").strip(),
                loc=p.get("locationsText",""), posted=p.get("postedOn",""),
                url=f"https://{ten}.{wd}.myworkdayjobs.com/{site}"+(p.get("externalPath") or ""),
                query=q))
        if len(posts)<limit: break
        time.sleep(0.4)
    return out
if __name__=="__main__":
    tenants=[l.strip().split("|") for l in open(sys.argv[1]) if l.strip()]
    queries=json.load(open(sys.argv[2]))
    jobs=[(t[0],t[1],t[2],q) for t in tenants for q in queries]
    rows=[]
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for r in ex.map(lambda a: search(*a), jobs): rows.extend(r)
    seen={}
    for r in rows:
        k=(r["company"],r["title"].lower())
        if k not in seen: seen[k]=r
    rows=list(seen.values())
    json.dump(rows,open(sys.argv[3],"w"),indent=1)
    print(f"workday: {len(tenants)} tenants x {len(queries)} queries -> {len(rows)} unique",file=sys.stderr)
