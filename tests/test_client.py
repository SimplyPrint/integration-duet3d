"""Tests for the VirtualClient class."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import aiohttp

import pytest

from .context import FileProgressStateEnum, DuetPrinter, DuetPrinterConfig
from simplyprint_ws_client.core.ws_protocol.messages import FileDemandData
from simplyprint_ws_client.core.state import PrinterStatus
from simplyprint_duet3d.duet.model import merge_dictionary


@pytest.fixture
def virtual_client():
    """Return a VirtualClient instance."""
    config = DuetPrinterConfig(
        id=1,
        token="token",
        unique_id="unique_id",
        duet_uri="http://example.com",
        duet_password="password",
        duet_unique_id="unique_id",
        webcam_uri="http://webcam.example.com",
    )
    client = DuetPrinter(config=config)
    return client


@pytest.mark.skip
@pytest.mark.asyncio
async def test_download_and_upload_file_progress_calculation(virtual_client):
    """Test that the file progress is calculated correctly."""
    event = FileDemandData(
        name="demand",
        demand="file",
    )
    event.url = "http://example.com/file.gcode"
    event.file_name = "file.gcode"
    event.auto_start = True

    mock_duet = AsyncMock()
    await virtual_client.init()
    virtual_client.duet = mock_duet
    virtual_client.on_start_print = Mock()
    asyncio.run_coroutine_threadsafe = Mock()
    virtual_client.event_loop = asyncio.get_event_loop()
    mock_duet.rr_upload_stream.return_value = {"err": 0}
    mock_duet.rr_fileinfo.return_value = {"err": 0}

    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value.read = AsyncMock(
            return_value=b"file content"
        )

        task = await virtual_client._download_file_from_sp_and_upload_to_duet(event)
        await task

        assert virtual_client.printer.file_progress.percent == 100.0
        assert virtual_client.printer.file_progress.state == FileProgressStateEnum.READY


@pytest.mark.skip
@pytest.mark.asyncio
async def test_download_and_upload_file_progress_between_90_and_100(virtual_client):
    """Test that the file progress is calculated correctly."""
    event = FileDemandData(
        name="demand",
        demand="file",
    )
    event.url = "http://example.com/file.gcode"
    event.file_name = "file.gcode"
    event.auto_start = True

    mock_duet = AsyncMock()
    virtual_client.duet = mock_duet
    virtual_client.on_start_print = Mock()
    virtual_client.event_loop = asyncio.get_event_loop()
    mock_duet.rr_upload_stream.return_value = {"err": 0}
    mock_duet.rr_fileinfo.side_effect = [{"err": 1}, {"err": 1}, {"err": 0}]
    asyncio.run_coroutine_threadsafe = Mock()

    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value.read = AsyncMock(
            return_value=b"file content"
        )

        expected_percent = iter([92.5, 98.75, 100.0])
        # Check the values this variable is set to

        def set_percent(change):
            value = next(expected_percent)
            assert value == change["new"]

        virtual_client.printer.file_progress.observe(
            set_percent,
            names=["percent"],
        )

        with patch("time.time", side_effect=[0, 0, 100, 100, 350, 350, 380]):
            task = await virtual_client._download_file_from_sp_and_upload_to_duet(event)
            await task

            assert virtual_client.printer.file_progress.percent == 100.0
            assert (
                virtual_client.printer.file_progress.state
                == FileProgressStateEnum.READY
            )
