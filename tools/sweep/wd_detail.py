import sys,json,re,html,urllib.request
UA={"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124 Safari/537.36","Accept":"application/json"}
def get(url):
    # url like https://humana.wd5.myworkdayjobs.com/Humana_External_Career_Site/job/...
    m=re.match(r"https://([^.]+)\.(wd\d+)\.myworkdayjobs\.com/([^/]+)(/.*)$",url)
    if not m: return None
    ten,wd,site,path=m.groups()
    cxs=f"https://{ten}.{wd}.myworkdayjobs.com/wday/cxs/{ten}/{site}{path}"
    try:
        r=urllib.request.Request(cxs,headers=UA)
        d=json.loads(urllib.request.urlopen(r,timeout=25).read().decode())
    except Exception as e: return {"err":str(e)}
    ji=d.get("jobPostingInfo",{}) or {}
    t=re.sub(r"<[^>]+>","\n",ji.get("jobDescription","") or "")
    t=html.unescape(t); t=re.sub(r"\n{2,}","\n",t).strip()
    return {"title":ji.get("title"),"loc":ji.get("location"),"posted":ji.get("startDate") or ji.get("postedOn"),
            "desc":t[:7000],"money":sorted(set(int(x.replace(",","")) for x in re.findall(r"\$\s?([\d]{2,3},\d{3})",t)))}
if __name__=="__main__":
    for u in sys.argv[1:]:
        r=get(u); print("="*90); print(u)
        if not r or r.get("err"): print("ERR",r); continue
        print(r["title"],"|",r["loc"],"|",r["posted"],"| bands:",r["money"])
        print(r["desc"][:4000])
