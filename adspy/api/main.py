from fastapi import FastAPI

from adspy.api.routes import search, bundles, alerts, billing

app = FastAPI(title="AdSpy", version="0.1.0")

app.include_router(search.router)
app.include_router(bundles.router)
app.include_router(alerts.router)
app.include_router(billing.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
