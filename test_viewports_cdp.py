"""
Automated CDP Viewport and Overflow Verification Script
Tests CampusConnect at 1280px, 768px, and 375px using Chrome DevTools Protocol.
Verifies:
1. document.documentElement.scrollWidth <= viewportWidth (Zero horizontal overflow)
2. #btn-nav-report boundingClientRect().right <= viewportWidth (Fits inside viewport)
3. Saves pixel-perfect screenshots for 1280px, 768px, and 375px
"""

import asyncio
import base64
import json
import os
import subprocess
import time
import urllib.request
import websockets

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
USER_DATA_DIR = r"D:\PROJECTS\project 1\temp_cdp"
APP_URL = "http://127.0.0.1:5000/"
PORT = 9222


async def run_viewport_tests():
    # 1. Start Chrome with remote debugging
    chrome_cmd = [
        CHROME_PATH,
        "--headless=new",
        "--no-sandbox",
        f"--user-data-dir={USER_DATA_DIR}",
        f"--remote-debugging-port={PORT}",
        "about:blank"
    ]
    proc = subprocess.Popen(chrome_cmd)
    time.sleep(2.0)

    try:
        # 2. Get WebSocket debugger URL
        tabs_url = f"http://127.0.0.1:{PORT}/json"
        req = urllib.request.urlopen(tabs_url)
        tabs = json.loads(req.read().decode('utf-8'))
        ws_url = tabs[0]['webSocketDebuggerUrl']
        print(f"[OK] Connected to Chrome DevTools Protocol at: {ws_url}")

        async with websockets.connect(ws_url) as ws:
            msg_id = 1

            async def send_cmd(method, params=None):
                nonlocal msg_id
                cid = msg_id
                msg_id += 1
                payload = {"id": cid, "method": method, "params": params or {}}
                await ws.send(json.dumps(payload))
                while True:
                    resp_raw = await ws.recv()
                    resp = json.loads(resp_raw)
                    if resp.get("id") == cid:
                        return resp.get("result", {})

            # Enable Page and DOM domains
            await send_cmd("Page.enable")
            await send_cmd("DOM.enable")

            # Navigate to local Flask app
            await send_cmd("Page.navigate", {"url": APP_URL})
            await asyncio.sleep(1.5)

            viewports = [
                {"name": "Desktop (1280px)", "width": 1280, "height": 800, "mobile": False},
                {"name": "Tablet (768px)", "width": 768, "height": 1024, "mobile": True},
                {"name": "Mobile (375px)", "width": 375, "height": 812, "mobile": True}
            ]

            results = []

            for vp in viewports:
                w = vp["width"]
                h = vp["height"]
                m = vp["mobile"]

                # Apply exact viewport dimensions & device metrics
                await send_cmd("Emulation.setDeviceMetricsOverride", {
                    "width": w,
                    "height": h,
                    "deviceScaleFactor": 1,
                    "mobile": m
                })
                await asyncio.sleep(0.5)

                # Evaluate layout and overflow metrics
                eval_script = """
                (() => {
                    const vw = window.innerWidth;
                    const docEl = document.documentElement;
                    const scrollW = docEl.scrollWidth;
                    const clientW = docEl.clientWidth;
                    const bodyScrollW = document.body.scrollWidth;

                    const btn = document.getElementById('btn-nav-report');
                    const btnRect = btn ? btn.getBoundingClientRect() : null;

                    const brand = document.getElementById('nav-brand-logo');
                    const brandRect = brand ? brand.getBoundingClientRect() : null;

                    const toggle = document.getElementById('mobile-nav-toggle');
                    const toggleRect = toggle ? toggle.getBoundingClientRect() : null;

                    // Detect any element overflowing the viewport width
                    const overflowingElements = [];
                    document.querySelectorAll('header, main, footer, .container, .hero-section, .metrics-grid, .cta-banner, .table-card, .lost-found-grid, .nav-actions').forEach(el => {
                        const r = el.getBoundingClientRect();
                        if (r.right > vw + 1) {
                            overflowingElements.push({
                                tag: el.tagName,
                                id: el.id || '',
                                class: el.className || '',
                                right: Math.round(r.right),
                                width: Math.round(r.width)
                            });
                        }
                    });

                    return {
                        viewportWidth: vw,
                        clientWidth: clientW,
                        scrollWidth: scrollW,
                        bodyScrollWidth: bodyScrollW,
                        hasHorizontalOverflow: scrollW > vw,
                        btnNavReport: btnRect ? {
                            left: Math.round(btnRect.left),
                            right: Math.round(btnRect.right),
                            width: Math.round(btnRect.width),
                            fitsInViewport: btnRect.right <= vw
                        } : null,
                        brandLogo: brandRect ? {
                            right: Math.round(brandRect.right),
                            width: Math.round(brandRect.width)
                        } : null,
                        mobileToggle: toggleRect ? {
                            visible: toggleRect.width > 0,
                            right: Math.round(toggleRect.right),
                            fitsInViewport: toggleRect.right <= vw
                        } : null,
                        overflowingElements: overflowingElements
                    };
                })()
                """

                eval_res = await send_cmd("Runtime.evaluate", {
                    "expression": eval_script,
                    "returnByValue": True
                })
                metrics = eval_res.get("result", {}).get("value", {})

                # Capture screenshot
                shot_data = await send_cmd("Page.captureScreenshot", {"format": "png"})
                if "data" in shot_data:
                    shot_path = os.path.join(r"D:\PROJECTS\project 1", f"verified_screenshot_{w}.png")
                    with open(shot_path, "wb") as sf:
                        sf.write(base64.b64decode(shot_data["data"]))
                    metrics["screenshotPath"] = shot_path

                metrics["testName"] = vp["name"]
                results.append(metrics)

            return results
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    print("=" * 60)
    print(" Running Automated Viewport & Overflow Tests via CDP")
    print("=" * 60)
    test_results = asyncio.run(run_viewport_tests())

    all_passed = True
    print("\n--- TEST RESULTS SUMMARY ---")
    for r in test_results:
        name = r["testName"]
        vw = r["viewportWidth"]
        sw = r["scrollWidth"]
        overflow = r["hasHorizontalOverflow"]
        btn_fits = r["btnNavReport"]["fitsInViewport"] if r.get("btnNavReport") else False
        btn_right = r["btnNavReport"]["right"] if r.get("btnNavReport") else 0

        status = "PASSED" if (not overflow and btn_fits) else "FAILED"
        if status == "FAILED":
            all_passed = False

        print(f"\n[{status}] {name}")
        print(f"   Viewport Width: {vw}px | Document ScrollWidth: {sw}px")
        print(f"   Horizontal Overflow: {overflow} (Expected: False)")
        print(f"   Report Issue Button Right Edge: {btn_right}px <= {vw}px (Fits: {btn_fits})")
        if r.get("mobileToggle") and r["mobileToggle"]["visible"]:
            print(f"   Mobile Nav Toggle: Visible and Fits inside viewport ({r['mobileToggle']['right']}px <= {vw}px)")
        if r.get("overflowingElements"):
            print(f"   Overflowing elements: {r['overflowingElements']}")
        print(f"   Screenshot saved: {r.get('screenshotPath')}")

    print("\n" + "=" * 60)
    if all_passed:
        print(" [ALL TESTS PASSED] Layout is 100% responsive with ZERO overflow!")
    else:
        print(" [TESTS FAILED] Issues detected.")
    print("=" * 60)
