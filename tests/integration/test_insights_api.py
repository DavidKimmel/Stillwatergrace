"""Integration tests for insights API endpoints."""


def test_recommendations_endpoint_exists():
    from api.main import app

    routes = [r.path for r in app.routes]
    assert "/api/analytics/insights/recommendations" in routes


def test_content_type_performance_endpoint_exists():
    from api.main import app

    routes = [r.path for r in app.routes]
    assert "/api/analytics/insights/content-type-performance" in routes


def test_format_performance_endpoint_exists():
    from api.main import app

    routes = [r.path for r in app.routes]
    assert "/api/analytics/insights/format-performance" in routes


def test_time_performance_endpoint_exists():
    from api.main import app

    routes = [r.path for r in app.routes]
    assert "/api/analytics/insights/time-performance" in routes


def test_competitor_activity_endpoint_exists():
    from api.main import app

    routes = [r.path for r in app.routes]
    assert "/api/analytics/insights/competitor-activity" in routes
