import statistics

def analyse_pulses(edges):
    durs=[e["duration_us"] for e in edges if 40 <= e["duration_us"] <= 200000]
    if not durs:
        return {"pulse_count":0}
    s=sorted(durs)
    med=statistics.median(s)
    short=[x for x in durs if x<=med]
    long=[x for x in durs if x>med]
    return {
        "pulse_count":len(durs),
        "min_us":min(s),
        "median_us":med,
        "max_us":max(s),
        "short_avg_us": round(statistics.mean(short),1) if short else None,
        "long_avg_us": round(statistics.mean(long),1) if long else None,
    }

def similarity(a,b):
    pa=[x["duration_us"] for x in a.get("pulses",[])]
    pb=[x["duration_us"] for x in b.get("pulses",[])]
    if not pa or not pb:
        return {"score":0.0,"note":"No pulse data"}
    n=min(len(pa),len(pb),500)
    pa=pa[:n]; pb=pb[:n]
    errs=[abs(x-y)/max(x,y,1) for x,y in zip(pa,pb)]
    score=max(0.0,100.0*(1.0-sum(errs)/len(errs)))
    return {
        "score":round(score,1),
        "compared_pulses":n,
        "note":"highly similar" if score>=85 else ("similar" if score>=70 else "different/variable")
    }
