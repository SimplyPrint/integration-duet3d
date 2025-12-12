import pytest
from unittest.mock import MagicMock
from .context import rescan_existing_networks


def test_rescan_existing_networks_ipv4():
    app = MagicMock()
    app.config_manager.get_all.return_value = [
        MagicMock(duet_uri="http://192.168.1.1", duet_password="password1"),
        MagicMock(duet_uri="http://192.168.2.1", duet_password="password2"),
    ]

    networks = rescan_existing_networks(app)

    expected_networks = {"192.168.1.0/24": "password1", "192.168.2.0/24": "password2"}
    assert networks == expected_networks


def test_rescan_existing_networks_ipv6():
    app = MagicMock()
    app.config_manager.get_all.return_value = [
        MagicMock(duet_uri="http://[2001:db8::1]", duet_password="password1")
    ]

    networks = rescan_existing_networks(app)

    expected_networks = {"2001:db8::/120": "password1"}
    assert networks == expected_networks


def test_rescan_existing_networks_dns_resolution_failure():
    app = MagicMock()
    app.config_manager.get_all.return_value = [
        MagicMock(duet_uri="http://invalid.hostname", duet_password="password1")
    ]

    with pytest.raises(ValueError):
        rescan_existing_networks(app)


def test_rescan_existing_networks_invalid_ip():
    app = MagicMock()
    app.config_manager.get_all.return_value = [
        MagicMock(duet_uri="http://999.999.999.999", duet_password="password1")
    ]

    with pytest.raises(ValueError):
        rescan_existing_networks(app)
