#!/usr/bin/env python3
import json, pathlib, urllib.request, urllib.error, hashlib, shutil, subprocess

OWNER="Pragsi"
REPO="sentinel"
CURRENT_VERSION="1.3.0"
API=f"https://api.github.com/repos/{OWNER}/{REPO}/releases/latest"
UA="Sentinel-Pi-Updater/1.3"
CACHE=pathlib.Path.home()/".sentinel"/"updates"
CACHE.mkdir(parents=True, exist_ok=True)

def _v(v):
    out=[]
    for part in v.lower().lstrip("v").split("."):
        n=""
        for c in part:
            if c.isdigit(): n+=c
            else: break
        out.append(int(n or 0))
    while len(out)<3: out.append(0)
    return tuple(out[:3])

def latest_release(timeout=8):
    req=urllib.request.Request(API,headers={
        "User-Agent":UA,
        "Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28",
    })
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:
            data=json.load(r)
    except urllib.error.HTTPError as e:
        if e.code==404:
            return {"available":False,"reason":"No GitHub release has been published yet."}
        raise
    tag=data.get("tag_name","")
    assets=data.get("assets",[])
    package=next((a for a in assets if a.get("name","").lower().endswith(".zip") and "sentinel" in a.get("name","").lower()),None)
    sha=next((a for a in assets if a.get("name","").lower().endswith(".sha256")),None)
    return {
        "available":_v(tag)>_v(CURRENT_VERSION),
        "current":CURRENT_VERSION,
        "latest":tag.lstrip("v"),
        "tag":tag,
        "notes":data.get("body") or "",
        "package":package,
        "sha_asset":sha,
    }

def _download(url,path):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/octet-stream"})
    with urllib.request.urlopen(req,timeout=30) as r, open(path,"wb") as f:
        shutil.copyfileobj(r,f)

def _sha256(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):
            h.update(b)
    return h.hexdigest()

def download_release(info):
    asset=info.get("package")
    if not asset:
        raise RuntimeError("Release has no Sentinel ZIP asset.")
    dest=CACHE/f"{info['tag']}-{asset['name']}"
    _download(asset["browser_download_url"],dest)
    digest=_sha256(dest)
    verified=False
    sha_asset=info.get("sha_asset")
    if sha_asset:
        shafile=CACHE/f"{info['tag']}-{sha_asset['name']}"
        _download(sha_asset["browser_download_url"],shafile)
        tokens=shafile.read_text(errors="ignore").replace("\n"," ").split()
        expected=next((t.lower() for t in tokens if len(t)==64 and all(c in "0123456789abcdefABCDEF" for c in t)),None)
        if expected:
            if digest.lower()!=expected:
                dest.unlink(missing_ok=True)
                raise RuntimeError("SHA-256 verification failed.")
            verified=True
    return {"path":str(dest),"sha256":digest,"verified":verified}

def install_release(path):
    return subprocess.run(
        ["pkexec","/usr/local/sbin/sentinel-update-helper",str(path)],
        capture_output=True,text=True
    )
