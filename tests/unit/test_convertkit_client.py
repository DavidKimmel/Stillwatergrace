from unittest.mock import patch, MagicMock
from core.email.convertkit_client import ConvertKitClient


@patch("core.email.convertkit_client.httpx.Client")
def test_get_subscriber_count(mock_client_cls: MagicMock) -> None:
    """Kit v4 API returns subscribers list + pagination object."""
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
    mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "subscribers": [{"id": i} for i in range(1)],
        "pagination": {"has_next_page": False},
    }
    mock_resp.raise_for_status = MagicMock()
    mock_client.get.return_value = mock_resp

    client = ConvertKitClient(api_key="test_key")
    count = client.get_subscriber_count()
    assert count == 1


@patch("core.email.convertkit_client.httpx.Client")
def test_get_subscriber_count_error_returns_zero(mock_client_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
    mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
    mock_client.get.side_effect = Exception("Network error")

    client = ConvertKitClient(api_key="test_key")
    count = client.get_subscriber_count()
    assert count == 0
