import logging
import os
from pathlib import Path

from api.try_text import load_env

_before = set(os.environ)
load_env(Path(__file__).resolve().parent.parent / ".env")  # before anything reads the env; a real env var wins
DOTENV_KEYS = set(os.environ) - _before  # api/conftest.py removes these after the api tests

import sentry_sdk  # noqa: E402
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import routes_bank, routes_cases, routes_eval, routes_ledger, routes_policy

if os.environ.get("SENTRY_DSN"):
    sentry_sdk.init(dsn=os.environ["SENTRY_DSN"], traces_sample_rate=1.0)

app = FastAPI(title="Proof of Purchase API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
for m in (routes_cases, routes_ledger, routes_policy, routes_bank, routes_eval):
    app.include_router(m.router)


@app.on_event("startup")
def _startup():
    from contextlib import closing
    from api import cases, db
    with closing(db.connect()) as conn:
        try:
            db.load_data_dir(conn)
        except Exception:  # a bad data file must not keep the API down; /data/reload reports it later
            logging.getLogger(__name__).exception("loading the data dir failed")
        db.record_policy(conn, cases.POLICY.version, [r.raw for r in cases.POLICY.rules])
    logging.getLogger("uvicorn.error").info("/check extractor: %s", cases._extractor()[0])
