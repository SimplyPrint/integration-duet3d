import pytest
from unittest.mock import AsyncMock, MagicMock
from simplyprint_duet3d.cli.autodiscover import get_webcam_url, download_dwc_file
from simplyprint_duet3d.duet.api import RepRapFirmware

import simplyprint_duet3d.cli.autodiscover

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
    simplyprint_duet3d.cli.autodiscover.download_dwc_file = mock_download_dwc_file
    #download_dwc_file = mock_download_dwc_file

    try:
        # Call the function
        result = await get_webcam_url(duet)

        # Assert the result
        assert result == "http://10.42.0.2:8081/0/stream?timestamp=1234567890"
    finally:
        # Restore the original function
        download_dwc_file = original_download_dwc_file
