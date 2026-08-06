#!/usr/bin/env python3
"""Mide el efecto de la tormenta de cache de simplify_access_management sobre
el tiempo de guardado (web_save) de un pago de transferencia interna
(account.payment, Bank -> Cash).

Fase A (baseline): N guardados con cache caliente.
Fase B (tormenta): antes de cada guardado se hace un GET /web, que ejecuta
registry.clear_all_caches() por la línea 61 del módulo — lo mismo que hace
cualquier usuario recargando Odoo en producción.

Uso: python3 measure_storm_simplify.py  (servidor en http://localhost:8072,
base test_v17_simplify_access_management, admin/admin)
"""
import json
import statistics
import time
import urllib.request

BASE = "http://localhost:8072"
DB = "test_v17_simplify_access_management"
REPS = 25

opener = urllib.request.build_opener()
session_cookie = None


def rpc(path, params):
    payload = json.dumps({"jsonrpc": "2.0", "method": "call", "params": params}).encode()
    req = urllib.request.Request(BASE + path, data=payload, headers={"Content-Type": "application/json"})
    if session_cookie:
        req.add_header("Cookie", session_cookie)
    with opener.open(req, timeout=120) as resp:
        body = json.loads(resp.read())
    if body.get("error"):
        raise RuntimeError(json.dumps(body["error"])[:500])
    return body["result"]


def call_kw(model, method, args, kwargs=None):
    return rpc("/web/dataset/call_kw/%s/%s" % (model, method), {
        "model": model, "method": method, "args": args, "kwargs": kwargs or {},
    })


# ── auth ──────────────────────────────────────────────────────────────────────
req = urllib.request.Request(
    BASE + "/web/session/authenticate",
    data=json.dumps({"jsonrpc": "2.0", "method": "call",
                     "params": {"db": DB, "login": "admin", "password": "admin"}}).encode(),
    headers={"Content-Type": "application/json"},
)
with opener.open(req, timeout=60) as resp:
    auth = json.loads(resp.read())
    cookie = resp.headers.get("Set-Cookie", "")
session_cookie = cookie.split(";")[0]
assert auth["result"]["uid"], "auth failed"

# ── datos base ────────────────────────────────────────────────────────────────
bank = call_kw("account.journal", "search_read", [[["type", "=", "bank"]], ["id"]], {"limit": 1})[0]
cash = call_kw("account.journal", "search_read", [[["type", "=", "cash"]], ["id"]], {"limit": 1})[0]


def save_once():
    vals = {
        "is_internal_transfer": True,
        "payment_type": "outbound",
        "journal_id": bank["id"],
        "destination_journal_id": cash["id"],
        "amount": 500.0,
    }
    t0 = time.perf_counter()
    rec = call_kw("account.payment", "web_save", [[], vals], {"specification": {"id": {}, "name": {}}})
    ms = (time.perf_counter() - t0) * 1000
    call_kw("account.payment", "unlink", [[rec[0]["id"]]])
    return ms


def hit_web():
    """GET /web autenticado: dispara registry.clear_all_caches() (línea 61)."""
    r = urllib.request.Request(BASE + "/web", headers={"Cookie": session_cookie})
    t0 = time.perf_counter()
    with opener.open(r, timeout=60) as resp:
        resp.read()
    return (time.perf_counter() - t0) * 1000


def run_phase(label, invalidate_before_each_save):
    times, web_times = [], []
    for _ in range(REPS):
        if invalidate_before_each_save:
            web_times.append(hit_web())
        times.append(save_once())
    ts = sorted(times)
    print("%s: n=%d  mediana=%.0f ms  p95=%.0f ms  max=%.0f ms" % (
        label, len(times), statistics.median(times), ts[int(len(ts) * 0.95) - 1], max(ts)))
    if web_times:
        print("   (GET /web con clear_all_caches: mediana %.0f ms)" % statistics.median(web_times))
    return statistics.median(times)


save_once()  # warm-up
m_base = run_phase("A) Cache caliente (sin tormenta)      ", False)
m_storm = run_phase("B) Cache invalidada antes de cada save", True)
print("factor mediana: x%.1f" % (m_storm / m_base))
