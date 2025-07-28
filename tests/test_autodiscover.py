import pytest
from unittest.mock import AsyncMock, MagicMock
from meltingplot.duet_simplyprint_connector.cli.autodiscover import get_webcam_url, download_dwc_file
from meltingplot.duet_simplyprint_connector.duet.api import RepRapFirmware

import meltingplot.duet_simplyprint_connector.cli.autodiscover

@pytest.mark.asyncio
async def test_get_webcam_url_with_hostname():
    # Mock the RepRapFirmware instance
    duet = MagicMock(spec=RepRapFirmware)
    duet.address = "http://10.42.0.2"

    # Mock the download_dwc_file function
    async def mock_download_dwc_file(duet):
        return {
            "main": {
                "webcam": {
                    "url": "http://[HOSTNAME]:8081/0/stream?timestamp=1234567890"
                }
            }
        }

    # Replace the actual download_dwc_file with the mock
    global download_dwc_file
    original_download_dwc_file = download_dwc_file
    meltingplot.duet_simplyprint_connector.cli.autodiscover.download_dwc_file = mock_download_dwc_file
    #download_dwc_file = mock_download_dwc_file

    try:
        # Call the function
        result = await get_webcam_url(duet)

        # Assert the result
        assert result == "http://10.42.0.2:8081/0/stream?timestamp=1234567890"
    finally:
        # Restore the original function
        download_dwc_file = original_download_dwc_file

@pytest.mark.asyncio
async def test_get_webcam_url_with_ipv6():
    # Mock the RepRapFirmware instance
    duet = MagicMock(spec=RepRapFirmware)
    duet.address = "http://[::1]:8080"

    # Mock the download_dwc_file function
    async def mock_download_dwc_file(duet):
        return {
            "main": {
                "webcam": {
                    "url": "http://[::1]:8081/0/stream?timestamp=1234567890"
                }
            }
        }

    # Replace the actual download_dwc_file with the mock
    global download_dwc_file
    original_download_dwc_file = download_dwc_file
    meltingplot.duet_simplyprint_connector.cli.autodiscover.download_dwc_file = mock_download_dwc_file
    #download_dwc_file = mock_download_dwc_file

    try:
        # Call the function
        result = await get_webcam_url(duet)

        # Assert the result
        assert result == "http://[::1]:8081/0/stream?timestamp=1234567890"
    finally:
        # Restore the original function
        download_dwc_file = original_download_dwc_file

@pytest.mark.asyncio
async def test_get_webcam_url_with_ipv6_hostname():
    # Mock the RepRapFirmware instance
    duet = MagicMock(spec=RepRapFirmware)
    duet.address = "http://[::1]:8080"

    # Mock the download_dwc_file function
    async def mock_download_dwc_file(duet):
        return {
            "main": {
                "webcam": {
                    "url": "http://[HOSTNAME]:8081/0/stream?timestamp=1234567890"
                }
            }
        }

    # Replace the actual download_dwc_file with the mock
    global download_dwc_file
    original_download_dwc_file = download_dwc_file
    meltingplot.duet_simplyprint_connector.cli.autodiscover.download_dwc_file = mock_download_dwc_file
    #download_dwc_file = mock_download_dwc_file

    try:
        # Call the function
        result = await get_webcam_url(duet)

        # Assert the result
        assert result == "http://[::1]:8081/0/stream?timestamp=1234567890"
    finally:
        # Restore the original function
        download_dwc_file = original_download_dwc_file


@pytest.mark.asyncio
async def test_get_webcam_url_with_hostname_and_params():
    # Mock the RepRapFirmware instance
    duet = MagicMock(spec=RepRapFirmware)
    duet.address = "http://duet-hostname:8080"

    # Mock the download_dwc_file function
    async def mock_download_dwc_file(duet):
        return {
            "main": {
                "webcam": {
                    "url": "http://[HOSTNAME]:8081/0/stream?timestamp=1234567890"
                }
            }
        }

    # Replace the actual download_dwc_file with the mock
    global download_dwc_file
    original_download_dwc_file = download_dwc_file
    meltingplot.duet_simplyprint_connector.cli.autodiscover.download_dwc_file = mock_download_dwc_file
    #download_dwc_file = mock_download_dwc_file

    try:
        # Call the function
        result = await get_webcam_url(duet)

        # Assert the result
        assert result == "http://duet-hostname:8081/0/stream?timestamp=1234567890"
    finally:
        # Restore the original function
        download_dwc_file = original_download_dwc_file


@pytest.mark.asyncio
async def test_get_webcam_url_without_hostname():
    # Mock the RepRapFirmware instance
    duet = MagicMock(spec=RepRapFirmware)
    duet.address = "http://duet-hostname:8080"

    # Mock the download_dwc_file function
    async def mock_download_dwc_file(duet):
        return {
            "main": {
                "webcam": {
                    "url": "/webcam"
                }
            }
        }

    # Replace the actual download_dwc_file with the mock
    global download_dwc_file
    original_download_dwc_file = download_dwc_file
    meltingplot.duet_simplyprint_connector.cli.autodiscover.download_dwc_file = mock_download_dwc_file
    #download_dwc_file = mock_download_dwc_file

    try:
        # Call the function
        result = await get_webcam_url(duet)

        # Assert the result
        assert result == "http://duet-hostname/webcam"
    finally:
        # Restore the original function
        download_dwc_file = original_download_dwc_file