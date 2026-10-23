"""SEO blueprint for XML sitemaps and robots.txt."""

from __future__ import annotations
from flask import Blueprint, Response, request

from app.services.sitemap_service import SitemapService

seo_bp = Blueprint("seo", __name__)


def _xml_response(body: str) -> Response:
    """Wrap XML content in a UTF-8 XML response."""
    return Response(f'<?xml version="1.0" encoding="UTF-8"?>\n{body}', content_type="application/xml; charset=utf-8")


@seo_bp.route("/sitemap_index.xml")
def sitemap_index():
    """Return XML sitemap index listing all sitemap chunk files."""
    body = SitemapService.generate_sitemap_index()
    return _xml_response(body)


@seo_bp.route("/sitemap_<int:page>.xml")
def sitemap_page(page: int):
    """Return a specific sitemap chunk with up to 1000 URL entries."""
    body = SitemapService.generate_sitemap_page(page)
    return _xml_response(body)


@seo_bp.route("/robots.txt")
def robots_txt():
    """Return robots.txt with sitemap pointer."""
    body = SitemapService.generate_robots_txt(request.host_url)
    return Response(body, content_type="text/plain; charset=utf-8")
