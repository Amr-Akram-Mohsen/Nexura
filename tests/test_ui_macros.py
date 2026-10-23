"""
Unit tests for generalized, composable UI primitives in templates/macros/ui.html:
- button (polymorphic <a> vs <button>, variants, caller slot, attrs)
- badge (polymorphic <a> vs <span>, dot indicators, caller slot)
- form (CSRF injection, method handling, caller slot)
- field (label, required indicator, error slot, caller slot)
- input & textarea (accessibility, error states, attrs)
- alert (variants, dismiss action, caller slot)
- modal (backdrop, dialog role, close trigger, caller slot)
"""
from __future__ import annotations
import pytest
from flask import render_template_string
from app import create_app


@pytest.fixture(scope="module")
def app():
    application = create_app()
    application.config["TESTING"] = True
    application.config["WTF_CSRF_ENABLED"] = True
    application.config["SECRET_KEY"] = "test-secret-key-for-csrf"
    yield application


def test_button_macro_button_and_link(app):
    with app.test_request_context("/"):
        # Test standard submit button
        tpl = """
        {% from "macros/ui.html" import button %}
        {{ button(text="Log In", type="submit", variant="gradient", size="lg", full=True, id="login-btn", attrs={"data-action": "submit-login"}) }}
        """
        html = render_template_string(tpl)
        assert "<button " in html
        assert 'type="submit"' in html
        assert 'id="login-btn"' in html
        assert "btn btn--gradient btn--lg btn--full" in html
        assert 'data-action="submit-login"' in html
        assert "<span>Log In</span>" in html

        # Test link button
        tpl_link = """
        {% from "macros/ui.html" import button %}
        {{ button(text="Go Home", href="/", variant="secondary", size="sm") }}
        """
        html_link = render_template_string(tpl_link)
        assert "<a " in html_link
        assert 'href="/"' in html_link
        assert "btn btn--secondary btn--sm" in html_link
        assert "<span>Go Home</span>" in html_link

        # Test caller block composition
        tpl_call = """
        {% from "macros/ui.html" import button %}
        {% call button(class="custom-btn") %}
          <span class="custom-badge">42</span>
        {% endcall %}
        """
        html_call = render_template_string(tpl_call)
        assert '<button type="button"' in html_call
        assert "custom-btn" in html_call
        assert '<span class="custom-badge">42</span>' in html_call


def test_badge_macro(app):
    with app.test_request_context("/"):
        # Static badge with dot
        tpl = """
        {% from "macros/ui.html" import badge %}
        {{ badge("Published", variant="ready", dot="green") }}
        """
        html = render_template_string(tpl)
        assert "<span " in html
        assert "badge badge--ready badge--pill-icon" in html
        assert '<span class="pulse-dot pulse-dot--green"></span>' in html
        assert "Published" in html

        # Linked badge
        tpl_link = """
        {% from "macros/ui.html" import badge %}
        {{ badge("Technology", href="/technology", variant="category") }}
        """
        html_link = render_template_string(tpl_link)
        assert "<a " in html_link
        assert 'href="/technology"' in html_link
        assert "badge badge--category" in html_link
        assert "Technology" in html_link


def test_form_and_field_primitives(app):
    with app.test_request_context("/"):
        tpl = """
        {% from "macros/ui.html" import form, field, input, textarea, button %}
        {% call form(action="/submit", method="post", class="test-form") %}
          {% call field(label="Email", for_id="email", required_mark=True, error="Invalid email") %}
            {{ input(name="email", id="email", type="email", value="test@example.com", required=True, error=True) }}
          {% endcall %}
          {% call field(label="Bio", for_id="bio", help_text="Short description") %}
            {{ textarea(name="bio", id="bio", rows=3, value="Hello world") }}
          {% endcall %}
          {{ button(text="Save", type="submit") }}
        {% endcall %}
        """
        html = render_template_string(tpl)
        assert '<form method="post" action="/submit" class="test-form"' in html
        assert 'name="csrf_token"' in html
        assert '<label class="auth-field__label" for="email">' in html
        assert '<span class="auth-field__required">*</span>' in html
        assert '<input class="auth-field__input error"' in html
        assert 'value="test@example.com"' in html
        assert '<span class="auth-field__error" role="alert">Invalid email</span>' in html
        assert '<textarea class="auth-field__input"' in html
        assert '<p class="field-help-text">Short description</p>' in html
        assert "Hello world</textarea>" in html


def test_alert_macro(app):
    with app.test_request_context("/"):
        tpl = """
        {% from "macros/ui.html" import alert %}
        {% call alert(title="Error Occurred", message="Cannot process request", type="error") %}
          <a href="/retry" class="retry-link">Retry Now</a>
        {% endcall %}
        """
        html = render_template_string(tpl)
        assert '<div class="alert alert--error"' in html
        assert 'role="alert"' in html
        assert '<strong class="alert__title">Error Occurred</strong>' in html
        assert '<div class="alert__message">Cannot process request</div>' in html
        assert '<a href="/retry" class="retry-link">Retry Now</a>' in html
        assert '<button type="button" class="alert__close"' in html


def test_modal_macro(app):
    with app.test_request_context("/"):
        tpl = """
        {% from "macros/ui.html" import modal, button %}
        {% call modal(id="confirm-modal", title="Confirm Action", close_action="close-modal") %}
          <p>Are you sure you want to proceed?</p>
          {{ button(text="Confirm", variant="danger", id="btn-ok") }}
        {% endcall %}
        """
        html = render_template_string(tpl)
        assert 'id="confirm-modal"' in html
        assert 'role="dialog"' in html
        assert 'aria-modal="true"' in html
        assert 'aria-labelledby="confirm-modal-title"' in html
        assert '<h2 class="confirm-modal__title" id="confirm-modal-title">Confirm Action</h2>' in html
        assert 'data-action="close-modal"' in html
        assert "<p>Are you sure you want to proceed?</p>" in html
        assert 'id="btn-ok"' in html
        assert "btn btn--danger" in html


def test_about_and_contact_pages_render(app):
    client = app.test_client()
    
    # Test About page
    res_about = client.get("/about")
    assert res_about.status_code == 200
    html_about = res_about.get_data(as_text=True)
    assert "The Nexura Pillars" in html_about
    assert "Multi-Format Discovery" in html_about
    assert "Editorial Quality Gates" in html_about
    assert "Structured Entity Taxonomy" in html_about
    assert "Privacy &amp; Speed First" in html_about or "Privacy & Speed First" in html_about
    assert "Browse Today&#39;s Stories" in html_about or "Browse Today's Stories" in html_about

    # Test Contact page GET
    res_contact = client.get("/contact")
    assert res_contact.status_code == 200
    html_contact = res_contact.get_data(as_text=True)
    assert "Direct Desks" in html_contact
    assert "Editorial &amp; Tips" in html_contact or "Editorial & Tips" in html_contact
    assert "tips@nexura.tech" in html_contact
    assert "contact-form" in html_contact
    assert 'name="name"' in html_contact
    assert 'name="email"' in html_contact
    assert 'name="message"' in html_contact
    assert "Send Message" in html_contact

    # Test Contact page POST submission with CSRF token
    import re
    match = re.search(r'name="csrf_token" value="([^"]+)"', html_contact)
    assert match is not None, "CSRF token must be present in contact form"
    csrf_token = match.group(1)

    res_submit = client.post("/contact", data={
        "csrf_token": csrf_token,
        "name": "Alex Rivers",
        "email": "alex@example.com",
        "topic": "tip",
        "message": "This is a confidential tip."
    })
    assert res_submit.status_code == 200
    html_submit = res_submit.get_data(as_text=True)
    assert "Message Sent Successfully" in html_submit
    assert "Send another message" in html_submit

