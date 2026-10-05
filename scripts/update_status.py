#!/usr/bin/env python3
"""Daily update for index.html.

1. Always sets "lastChecked" to the current UK time.
2. Looks up each celebrity on Wikipedia/Wikidata and adds anyone with a
   2026 date of death that is not already in the tally.
Standard library only, so the GitHub Action needs no installs.
"""
import json, re, sys, urllib.parse, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

UA = {"User-Agent": "snuffclub-daily-check/1.0 (https://github.com/Johno78/snuffclub)"}
YEAR = "2026"

# name on the list -> English Wikipedia article title
TITLES = {
 "Johnny Mathis":"Johnny Mathis","Sheila Hancock":"Sheila Hancock","Yoko Ono":"Yoko Ono",
 "Douglas Hurd":"Douglas Hurd","Herb Alpert":"Herb Alpert","Graham Kerr":"Graham Kerr",
 "James Bolam":"James Bolam","Susan Hampshire":"Susan Hampshire","Bill Wyman":"Bill Wyman",
 "Vanessa Redgrave":"Vanessa Redgrave","Tom Courtenay":"Tom Courtenay",
 "Engelbert Humperdinck":"Engelbert Humperdinck (singer)","Tippi Hedren":"Tippi Hedren",
 "Virginia McKenna":"Virginia McKenna","Wendy Craig":"Wendy Craig","Claire Bloom":"Claire Bloom",
 "Nanette Newman":"Nanette Newman","Richard Wilson":"Richard Wilson (Scottish actor)",
 "William Roache":"William Roache","Joan Collins":"Joan Collins","Willie Nelson":"Willie Nelson",
 "Barbara Knox":"Barbara Knox","Bill Cosby":"Bill Cosby","Derek Jacobi":"Derek Jacobi",
 "Jane Fonda":"Jane Fonda","Shirley MacLaine":"Shirley MacLaine","Imelda Marcos":"Imelda Marcos",
 "Robert Duvall":"Robert Duvall","Stuart Hall":"Stuart Hall (presenter)","Woody Allen":"Woody Allen",
 "Judi Dench":"Judi Dench","Morgan Freeman":"Morgan Freeman","Phyllida Law":"Phyllida Law",
 "Warren Beatty":"Warren Beatty","Tom Baker":"Tom Baker","Ursula Andress":"Ursula Andress",
 "Dustin Hoffman":"Dustin Hoffman","Jack Nicholson":"Jack Nicholson","William Shatner":"William Shatner",
 "Kim Novak":"Kim Novak","Judy Parfitt":"Judy Parfitt","Frankie Valli":"Frankie Valli",
 "Princess Alexandra":"Princess Alexandra, The Honourable Lady Ogilvy","Gary Player":"Gary Player",
 "Amanda Barrie":"Amanda Barrie","Dick Van Dyke":"Dick Van Dyke","Clint Eastwood":"Clint Eastwood",
 "Josef Fritzl":"Josef Fritzl","Michael Caine":"Michael Caine","Rupert Murdoch":"Rupert Murdoch",
 "Ellen Burstyn":"Ellen Burstyn","Shirley Bassey":"Shirley Bassey","Sophia Loren":"Sophia Loren",
 "Roman Polanski":"Roman Polanski","Julian Glover":"Julian Glover","Robert Wagner":"Robert Wagner",
 "Harriet Andersson":"Harriet Andersson","Petula Clark":"Petula Clark","Eileen Atkins":"Eileen Atkins",
 "Anthony Hopkins":"Anthony Hopkins","Julie Andrews":"Julie Andrews","Buzz Aldrin":"Buzz Aldrin",
 "Ridley Scott":"Ridley Scott","Edward Fox":"Edward Fox (actor)","Joan Bakewell":"Joan Bakewell",
 "Anne Reid":"Anne Reid","Dennis Skinner":"Dennis Skinner","Mary Berry":"Mary Berry",
 "Michael Aspel":"Michael Aspel","Pat Boone":"Pat Boone","Michael Heseltine":"Michael Heseltine",
 "Jim Dale":"Jim Dale","Tommy Steele":"Tommy Steele","Annette Crosbie":"Annette Crosbie",
 "Angie Dickinson":"Angie Dickinson","Judd Hirsch":"Judd Hirsch","Brian Blessed":"Brian Blessed",
 "Thelma Barlow":"Thelma Barlow","Sian Phillips":"Sian Phillips","Shani Wallis":"Shani Wallis",
 "Barbara Eden":"Barbara Eden","Akihito":"Akihito","Eileen Derbyshire":"Eileen Derbyshire",
 "Tom Skerritt":"Tom Skerritt","David Attenborough":"David Attenborough",
 "Bernie Ecclestone":"Bernie Ecclestone","Len Deighton":"Len Deighton",
 "Edward Duke of Kent":"Prince Edward, Duke of Kent",
}

def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def wiki_items(titles):
    """title -> (wikidata id, resolved title, is_disambiguation)"""
    out = {}
    names = list(titles)
    for i in range(0, len(names), 40):
        chunk = names[i:i+40]
        url = ("https://en.wikipedia.org/w/api.php?action=query&format=json&redirects=1"
               "&prop=pageprops&ppprop=wikibase_item|disambiguation&titles="
               + urllib.parse.quote("|".join(chunk)))
        data = get(url)["query"]
        redirect = {}
        for key in ("normalized", "redirects"):
            for r in data.get(key, []):
                redirect[r["from"]] = r["to"]
        pages = {p["title"]: p for p in data["pages"].values()}
        for t in chunk:
            cur = t
            for _ in range(3):
                cur = redirect.get(cur, cur)
            p = pages.get(cur)
            if not p:
                continue
            props = p.get("pageprops", {})
            out[t] = (props.get("wikibase_item"), p["title"], "disambiguation" in props)
    return out

def wikidata(ids):
    out = {}
    ids = sorted(set(i for i in ids if i))
    for i in range(0, len(ids), 40):
        chunk = ids[i:i+40]
        url = ("https://www.wikidata.org/w/api.php?action=wbgetentities&format=json"
               "&props=claims&ids=" + "|".join(chunk))
        out.update(get(url).get("entities", {}))
    return out

def claim_time(ent, prop):
    for c in ent.get("claims", {}).get(prop, []):
        snak = c.get("mainsnak", {})
        if snak.get("snaktype") == "value":
            return snak["datavalue"]["value"]["time"], snak["datavalue"]["value"].get("precision", 0)
    return None, 0

def is_human(ent):
    for c in ent.get("claims", {}).get("P31", []):
        v = c.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        if v.get("id") == "Q5":
            return True
    return False

def parse(t):
    m = re.match(r"^[+-](\d{4})-(\d\d)-(\d\d)", t)
    return int(m.group(1)), int(m.group(2)), int(m.group(3))

def main(path="index.html"):
    html = open(path, encoding="utf-8").read()
    pat = re.compile(r'(<script type="application/json" id="state">)(.*?)(</script>)', re.S)
    m = pat.search(html)
    state = json.loads(m.group(2))
    have = {d["name"] for d in state["deaths"]}
    added = []
    try:
        items = wiki_items(TITLES.values())
        ents = wikidata(v[0] for v in items.values())
        for name, title in TITLES.items():
            if name in have or title not in items:
                continue
            qid, resolved, disamb = items[title]
            if disamb or not qid or qid not in ents:
                print("skip (no clean match):", name)
                continue
            ent = ents[qid]
            if not is_human(ent):
                print("skip (not a human item):", name)
                continue
            died, prec = claim_time(ent, "P570")
            if not died or prec < 11 or not died.lstrip("+").startswith(YEAR):
                continue
            y, mo, d = parse(died)
            born, bprec = claim_time(ent, "P569")
            age = None
            if born and bprec >= 11:
                by, bm, bd = parse(born)
                age = y - by - ((mo, d) < (bm, bd))
            date_txt = datetime(y, mo, d).strftime("%-d %B %Y")
            added.append(name)
            state["deaths"].append({
                "name": name, "date": date_txt, "age": age,
                "source": "Wikipedia",
                "sourceUrl": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(resolved.replace(" ", "_")),
            })
    except Exception as e:  # a failed lookup must never stop the time updating
        print("lookup failed:", repr(e))
    now = datetime.now(ZoneInfo("Europe/London"))
    state["lastChecked"] = now.strftime("%-d %B %Y, %H:%M")
    new = pat.sub(lambda x: x.group(1) + json.dumps(state, ensure_ascii=False, separators=(",", ":")) + x.group(3), html, count=1)
    open(path, "w", encoding="utf-8").write(new)
    print("lastChecked:", state["lastChecked"], "| deaths:", len(state["deaths"]), "| new:", added)

if __name__ == "__main__":
    main(*sys.argv[1:])
