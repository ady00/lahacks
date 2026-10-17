import os

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import routes_bank, routes_cases, routes_eval, routes_ledger, routes_policy

if os.environ.get("SENTRY_DSN"):
    sentry_sdk.init(dsn=os.environ["SENTRY_DSN"], traces_sample_rate=1.0)

app = FastAPI(title="Proof of Purchase API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
for m in (routes_cases, routes_ledger, routes_policy, routes_bank, routes_eval):
    app.include_router(m.router)
