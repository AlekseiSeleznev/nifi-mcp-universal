"""Exercise certificate settings through the rendered dashboard in Chromium."""

import os
from pathlib import Path
import sys

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "gateway"))
from gateway.web_ui_helpers import render_dashboard


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        channel = os.environ.get("NIFI_TEST_BROWSER_CHANNEL")
        instance = playwright.chromium.launch(channel=channel or None)
        yield instance
        instance.close()


@pytest.fixture
def page(browser):
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()


def serve_dashboard(page, profile, saved):
    def route(request):
        path = request.request.url.split("?")[0].rsplit("/", 1)[-1]
        if path == "connections":
            request.fulfill(json=[profile])
        elif path == "status":
            request.fulfill(json={"active_default": profile["name"]})
        elif path == "edit":
            saved.append(request.request.post_data)
            request.fulfill(json={"ok": True})
        else:
            request.fulfill(content_type="text/html", body=render_dashboard("en"))

    page.route("http://dashboard.test/**", route)
    page.goto("http://dashboard.test/dashboard")
    page.locator(".db-name").wait_for()


@pytest.mark.parametrize("auth_method", ["certificate_p12", "certificate_pem"])
@pytest.mark.parametrize("verify_ssl", [True, False])
def test_edit_keeps_saved_certificate_settings(page, auth_method, verify_ssl):
    profile = {
        "name": "saved-certificate", "url": "https://nifi.example.test/nifi-api",
        "auth_method": auth_method, "verify_ssl": verify_ssl, "readonly": True,
        "cert_path": "saved-certificate/client.p12", "cert_key_path": "client.key",
        "cert_password": "***", "connected": True, "nifi_version": "2.11.0",
    }
    saved = []
    serve_dashboard(page, profile, saved)
    page.get_by_role("button", name="Edit", exact=True).click()
    assert page.locator("#e-ssl").is_checked() is verify_ssl
    assert not page.locator("#e-aw").is_checked()
    if auth_method == "certificate_p12":
        assert page.locator("#e-certpw").input_value() == ""
        assert page.locator("#e-certpw").get_attribute("placeholder") == "••••••"
    with page.expect_response("**/api/edit"):
        page.get_by_role("button", name="Save", exact=True).click()
    assert len(saved) == 1
    assert 'name="verify_ssl"\r\n\r\n' + str(verify_ssl).lower() in saved[0]
    assert 'name="readonly"\r\n\r\ntrue' in saved[0]
    assert 'name="cert_password"' not in saved[0]


@pytest.mark.parametrize("auth_method", ["certificate_p12", "certificate_pem"])
@pytest.mark.parametrize("verify_ssl", [True, False])
def test_selecting_certificate_keeps_explicit_tls_choice(page, auth_method, verify_ssl):
    serve_dashboard(page, {"name": "existing", "url": "", "auth_method": "none"}, [])
    if page.locator("#f-ssl").is_checked() is not verify_ssl:
        page.locator("label.toggle").filter(has=page.locator("#f-ssl")).click()
    page.locator("#f-auth").select_option(auth_method)
    assert page.locator("#f-ssl").is_checked() is verify_ssl
