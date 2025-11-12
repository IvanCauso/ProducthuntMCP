import os, requests
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

PH_TOKEN = os.environ.get("PRODUCTHUNT_TOKEN")
PH_URL = "https://api.producthunt.com/v2/api/graphql"
HDRS = {"Authorization": f"Bearer {PH_TOKEN}", "Content-Type": "application/json"}

app = FastAPI()

def iso_day_bounds(day_str: str):
    # UTC day start and next-day start (PH treats postedBefore as exclusive)
    start = datetime.fromisoformat(day_str).replace(tzinfo=timezone.utc)
    before = start + timedelta(days=1)
    return start.isoformat().replace("+00:00","Z"), before.isoformat().replace("+00:00","Z")

Q = """
query($after: DateTime!, $before: DateTime!, $first: Int!, $cursor: String) {
  posts(postedAfter: $after, postedBefore: $before, first: $first, after: $cursor) {
    edges {
      node {
        id name tagline votesCount createdAt website slug
        makers { name username }
      }
    }
    pageInfo { endCursor hasNextPage }
  }
}
"""

def fetch_day(day_str: str):
    if not PH_TOKEN:
        raise HTTPException(500, "PRODUCTHUNT_TOKEN is not set")
    after, before = iso_day_bounds(day_str)
    items, cursor = [], None
    while True:
        body = {"query": Q, "variables": {"after": after, "before": before, "first": 30, "cursor": cursor}}
        r = requests.post(PH_URL, headers=HDRS, json=body, timeout=30)
        if not r.ok:
            raise HTTPException(r.status_code, r.text)
        data = r.json().get("data", {}).get("posts", {})
        items += [e["node"] for e in data.get("edges", [])]
        page = data.get("pageInfo") or {}
        if not page.get("hasNextPage") or len(items) >= 100:
            break
        cursor = page.get("endCursor")
    return items[:100]

@app.get("/", response_class=HTMLResponse)
def root():
    return HTMLResponse("OK<br>Use /ph?start=YYYY-MM-DD&end=YYYY-MM-DD&fmt=html|json")

@app.get("/ph")
def ph(start: str = Query(...), end: str | None = Query(None), fmt: str = Query("html")):
    end = end or start
    # iterate days inclusive
    start_d = datetime.fromisoformat(start).date()
    end_d = datetime.fromisoformat(end).date()
    day = start_d
    all_items = []
    while day <= end_d:
        all_items += fetch_day(day.isoformat())
        day += timedelta(days=1)

    if fmt == "json":
        return JSONResponse(all_items)

    rows = []
    for p in all_items:
        makers = ", ".join([m["name"] for m in p.get("makers") or []])
        rows.append(f"""
          <tr>
            <td>{p.get('name','')}</td>
            <td>{p.get('tagline','')}</td>
            <td>{p.get('votesCount','')}</td>
            <td>{p.get('createdAt','')}</td>
            <td><a href="{p.get('website','')}">{p.get('website','')}</a></td>
            <td>{makers}</td>
          </tr>
        """)
    html = f"""
      <html><body>
      <h1>Product Hunt launches {start} to {end}</h1>
      <table border="1" cellpadding="6">
        <thead><tr><th>Name</th><th>Tagline</th><th>Votes</th><th>Date</th><th>Website</th><th>Makers</th></tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
      </body></html>
    """
    return HTMLResponse(html)
