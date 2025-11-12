import os, requests
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse

PH_TOKEN = os.environ.get("PRODUCTHUNT_TOKEN")

Q = """
query($start: DateTime!, $end: DateTime!) {
  posts(postedAfter: $start, postedBefore: $end, first: 100, order: VOTES_COUNT) {
    edges {
      node {
        id
        name
        tagline
        votesCount
        createdAt
        website
        makers { name username }
      }
    }
  }
}
"""

def fetch_ph(start: str, end: str):
    if not PH_TOKEN:
        raise HTTPException(500, "PRODUCTHUNT_TOKEN is not set on the server")
    r = requests.post(
        "https://api.producthunt.com/v2/api/graphql",
        headers={"Authorization": f"Bearer {PH_TOKEN}", "Content-Type": "application/json"},
        json={"query": Q, "variables": {"start": f"{start}T00:00:00Z", "end": f"{end}T23:59:59Z"}}
    )
    if not r.ok:
        raise HTTPException(r.status_code, r.text)
    data = r.json()
    edges = data.get("data", {}).get("posts", {}).get("edges", [])
    return [e["node"] for e in edges]

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def root():
    return HTMLResponse("<html><body><h1>OK</h1><p>Use /ph?start=YYYY-MM-DD&end=YYYY-MM-DD&fmt=html|json</p></body></html>")

@app.get("/ph")
def ph(start: str = Query(...), end: str | None = Query(None), fmt: str = Query("html")):
    end = end or start
    items = fetch_ph(start, end)
    if fmt == "json":
        return JSONResponse(items)
    rows = []
    for p in items:
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
