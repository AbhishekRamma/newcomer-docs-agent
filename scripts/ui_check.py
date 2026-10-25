"""Drive the real UI in headless Chromium: sign in through Keycloak as the demo user, ask a
cached question and a refusal, open history, reload (silent sign-in), sign out. Saves three
screenshots to OUT_DIR (default docs/) and prints a JSON summary with no tokens in it.

Needs the hostnet stack running with LLM_PROVIDER=cached. Uses the local demo credentials
from keycloak/realm-newcomer.json (demo-only, not a secret).
Run: uv run --no-project --with playwright python scripts/ui_check.py
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

WEB = "http://localhost:5173"
Q = "What identification do I need to open a bank account in Canada?"
OUT = os.getenv("OUT_DIR", "docs")
R = "My landlord is evicting me without notice. Can I sue him, and what should I say in court?"
out = {}
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    console = []
    page.on("console", lambda m: console.append(f"{m.type}: {m.text}"[:200]))
    page.goto(WEB)
    page.get_by_role("button", name="Sign in").wait_for(timeout=20000)
    page.screenshot(path=OUT + "/web_login.png")
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_url("**/realms/newcomer/**", timeout=20000)
    out["keycloak_login_url_has_pkce"] = "code_challenge_method=S256" in page.url
    page.fill("#username", "demo")
    page.fill("#password", "demo-only-not-a-secret")
    page.click("#kc-login")
    page.wait_for_url(WEB + "/", timeout=20000)
    page.get_by_role("button", name="Sign out").wait_for(timeout=20000)
    out["header_user"] = page.locator(".who").inner_text()
    out["url_after_callback"] = page.url  # code/state should be gone
    # tokens must not be in web storage
    storage = page.evaluate("() => JSON.stringify({l: {...localStorage}, s: {...sessionStorage}})")
    st = json.loads(storage)
    out["localStorage_keys"] = list(st["l"].keys())
    out["sessionStorage_keys"] = list(st["s"].keys())
    out["access_token_in_web_storage"] = "access_token" in storage
    page.fill("#q", Q)
    page.click("button.gel")
    page.locator(".msg.bot:not(.loading)").last.wait_for(timeout=60000)
    page.fill("#q", R)
    page.click("button.gel")
    page.locator(".msg.bot:not(.loading)").nth(1).wait_for(timeout=60000)
    out["cite_links"] = page.locator("a.cite").count()
    out["refusal_tags"] = page.locator(".msg.refusal .tag").all_inner_texts()
    h = page.evaluate("() => document.documentElement.scrollHeight")
    page.set_viewport_size({"width": 1280, "height": h})
    page.wait_for_timeout(300)
    page.screenshot(path=OUT + "/web_chat.png")
    page.set_viewport_size({"width": 1280, "height": 900})
    page.get_by_role("button", name="History").click()
    page.locator(".hist").first.wait_for(timeout=20000)
    page.locator(".hist summary").first.click()
    out["history_rows"] = page.locator(".hist").count()
    page.screenshot(path=OUT + "/web_history.png")
    # refresh: in-memory tokens are lost; silent sign-in via the Keycloak session should restore
    page.reload()
    try:
        page.get_by_role("button", name="Sign out").wait_for(timeout=15000)
        out["after_refresh"] = "signed in again silently"
    except Exception:
        login = page.get_by_role("button", name="Sign in").count()
        out["after_refresh"] = "login screen shown" if login else "unknown"
    out["console_after_refresh"] = console[-8:]
    if out["after_refresh"] != "signed in again silently":
        print(json.dumps(out, indent=2))
        sys.exit(1)
    # sign out
    page.get_by_role("button", name="Sign out").click()
    page.get_by_role("button", name="Sign in").wait_for(timeout=20000)
    out["after_sign_out"] = "login screen"
    page.reload()
    page.wait_for_timeout(3000)
    login = page.get_by_role("button", name="Sign in").count()
    out["after_sign_out_refresh"] = "login screen" if login else "signed in"
    out["console_errors"] = [c for c in console if c.startswith("error")][:5]
    b.close()
print(json.dumps(out, indent=2))
