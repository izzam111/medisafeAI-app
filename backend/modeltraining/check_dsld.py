"""Quick check of the NIH DSLD API: one search and one label. Prints what the server answers."""
import json, urllib.request, urllib.error

def get(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 MediSafe-FYP", "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, r.read().decode(errors="ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors="ignore")
    except Exception as e:
        return e.__class__.__name__, str(e)

code, body = get("https://api.ods.od.nih.gov/dsld/v9/search-filter?q=iron&size=2")
print("SEARCH:", code)
try:
    data = json.loads(body)
    hits = data.get("hits", [])
    hits = hits.get("hits", hits) if isinstance(hits, dict) else hits
    first = hits[0]
    print("hit keys:", list(first)); print("_id:", first.get("_id"))
    print("_source keys:", list(first.get("_source", {})))
    src = first.get("_source", {})
    print("first ingredient:", json.dumps((src.get("allIngredients") or [None])[0])[:300])
    lid = first.get("_id")
except Exception as e:
    print("could not read search:", e, body[:300]); lid = None

for url in [f"https://api.ods.od.nih.gov/dsld/v9/label/{lid}", f"https://api.ods.od.nih.gov/dsld/v8/label/{lid}"]:
    code, body = get(url)
    print("\nLABEL", url.split("/dsld/")[1], "->", code)
    print(body[:400])
