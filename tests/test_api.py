import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

import aiohttp

from .context import RepRapFirmware
from meltingplot.duet_simplyprint_connector.duet.base import DuetAPIBase


@pytest.fixture
def mock_session():
    session = AsyncMock(aiohttp.ClientSession)
    session.get.return_value.__aenter__.return_value.json = AsyncMock(return_value={'err': 0})
    session.post.return_value.__aenter__.return_value.read = AsyncMock(return_value=b'Response')
    session.post.return_value.__aenter__.return_value.json = AsyncMock(return_value={'err': 0})
    session.get.return_value.__aenter__.return_value.text = AsyncMock(return_value='Response')
    session.closed = False
    return session


@pytest.fixture
def reprapfirmware(mock_session):
    return RepRapFirmware(session=mock_session)


@pytest.mark.asyncio
async def test_connect(reprapfirmware, mock_session):
    response = await reprapfirmware.connect()
    assert response == {'err': 0}
    mock_session.get.assert_called_once_with('http://10.42.0.2/rr_connect', params={'password': 'meltingplot', 'sessionKey': 'yes'})


@pytest.mark.asyncio
async def test_disconnect(reprapfirmware, mock_session):
    response = await reprapfirmware.disconnect()
    assert response == {'err': 0}
    mock_session.get.assert_called_once_with('http://10.42.0.2/rr_disconnect')


@pytest.mark.asyncio
async def test_rr_model(reprapfirmware, mock_session):
    response = await reprapfirmware.rr_model(key='test', frequently=True, verbose=True, depth=99, array=10)
    assert response == {'err': 0}
    mock_session.get.assert_called_once_with('http://10.42.0.2/rr_model', params={'key': 'test', 'flags': 'fvd99a10'})


@pytest.mark.asyncio
async def test_rr_gcode(reprapfirmware, mock_session):
    orig_reply = reprapfirmware.rr_reply
    reprapfirmware.rr_reply = AsyncMock(return_value='Response')
    response = await reprapfirmware.rr_gcode('G28')
    assert response == 'Response'
    mock_session.get.assert_called_once_with('http://10.42.0.2/rr_gcode', params={'gcode': 'G28'})
    reprapfirmware.rr_reply = orig_reply


@pytest.mark.asyncio
async def test_rr_reply(reprapfirmware, mock_session):
    response = await reprapfirmware.rr_reply()
    assert response == 'Response'
    mock_session.get.assert_called_once_with('http://10.42.0.2/rr_reply')


@pytest.mark.asyncio
async def test_rr_download(reprapfirmware, mock_session):
    async def chunks(size):
        data = [b'chunk1', b'chunk2']
        for item in data:
            yield item

    mock_session.get.return_value.__aenter__.return_value.content.iter_chunked = chunks
    async for _ in reprapfirmware.rr_download('test.txt'):
        break

    #async for chunk in reprapfirmware.rr_download('test.txt'):
    #    assert chunk in chunks
    mock_session.get.assert_called_once_with('http://10.42.0.2/rr_download', params={'name': 'test.txt'})


@pytest.mark.asyncio
async def test_rr_upload(reprapfirmware, mock_session):
    content = b'testtttttt'
    response = await reprapfirmware.rr_upload('test.txt', content)
    assert response == {'err': 0}
    mock_session.post.assert_called_once_with('http://10.42.0.2/rr_upload', data=content, params={'name': 'test.txt', 'crc32': '075b1c7c'}, headers={'Content-Length': '10'})


@pytest.mark.asyncio
async def test_rr_upload_stream(reprapfirmware, mock_session):
    file = MagicMock()
    file.tell.return_value = 10
    file.read.side_effect = [b'chunk1', b'chunk2', b'']
    mock_session.reset_mock()
    response = await reprapfirmware.rr_upload_stream('test.txt', file)
    assert response == {'err': 0}
    mock_session.post.assert_called_once()
    assert mock_session.post.call_args[1]['url'] == 'http://10.42.0.2/rr_upload'
    assert mock_session.post.call_args[1]['params'] == {'name': 'test.txt', 'crc32': 'be0e1d1b'}


@pytest.mark.asyncio
async def test_rr_filelist(reprapfirmware, mock_session):
    response = await reprapfirmware.rr_filelist('/path/to/directory')
    assert response == {'err': 0}
    mock_session.get.assert_called_once_with('http://10.42.0.2/rr_filelist', params={'dir': '/path/to/directory'})


@pytest.mark.asyncio
async def test_rr_fileinfo(reprapfirmware, mock_session):
    response = await reprapfirmware.rr_fileinfo('test.txt')
    assert response == {'err': 0}
    mock_session.get.assert_called_once_with('http://10.42.0.2/rr_fileinfo', params={'name': 'test.txt'})


@pytest.mark.asyncio
async def test_rr_mkdir(reprapfirmware, mock_session):
    response = await reprapfirmware.rr_mkdir('/path/to/directory')
    assert response == {'err': 0}
    mock_session.get.assert_called_once_with('http://10.42.0.2/rr_mkdir', params={'dir': '/path/to/directory'})

@pytest.mark.asyncio
async def test_reconnect_success(reprapfirmware, mock_session):
    response = await reprapfirmware.reconnect()
    assert response == {'err': 0}
    mock_session.get.assert_called_once_with('http://10.42.0.2/rr_connect', params={'password': 'meltingplot', 'sessionKey': 'yes'})

@pytest.mark.skip
@pytest.mark.asyncio
async def test_reconnect_multiple_calls(reprapfirmware, mock_session):
    # Simulate multiple reconnect calls
    # TODO make mock_session make a context switch/yield to make the test work
    mock_session.get.return_value.__aenter__.return_value.json.side_effect = lambda: asyncio.sleep(1)
    responses = await asyncio.gather(reprapfirmware.reconnect(), reprapfirmware.reconnect(), reprapfirmware.reconnect())
    for response in responses:
        assert response == {'err': 0}
    mock_session.get.assert_called_once_with('http://10.42.0.2/rr_connect', params={'password': 'meltingplot', 'sessionKey': 'yes'})

@pytest.mark.asyncio
async def test_reconnect_with_session_key(reprapfirmware, mock_session):
    mock_session.get.return_value.__aenter__.return_value.json = AsyncMock(return_value={'err': 0, 'sessionKey': 'test_key'})
    response = await reprapfirmware.reconnect()
    assert response == {'err': 0, 'sessionKey': 'test_key'}
    #assert reprapfirmware.session.headers['X-Session-Key'] == 'test_key'
    mock_session.get.assert_called_once_with('http://10.42.0.2/rr_connect', params={'password': 'meltingplot', 'sessionKey': 'yes'})

@pytest.mark.asyncio
async def test_reconnect_with_session_timeout(reprapfirmware, mock_session):
    mock_session.get.return_value.__aenter__.return_value.json = AsyncMock(return_value={'err': 0, 'sessionTimeout': 10000})
    response = await reprapfirmware.reconnect()
    assert response == {'err': 0, 'sessionTimeout': 10000}
    assert reprapfirmware.session_timeout == 10000
    mock_session.get.assert_called_once_with('http://10.42.0.2/rr_connect', params={'password': 'meltingplot', 'sessionKey': 'yes'})


def test_reprapfirmware_is_duet_api_base(reprapfirmware):
    assert isinstance(reprapfirmware, DuetAPIBase)


@pytest.mark.asyncio
async def test_send_gcode(reprapfirmware, mock_session):
    reprapfirmware.rr_reply = AsyncMock(return_value='ok')
    result = await reprapfirmware.send_gcode('G28', no_reply=True)
    assert result == ''


@pytest.mark.asyncio
async def test_send_gcode_with_reply(reprapfirmware, mock_session):
    reprapfirmware.rr_reply = AsyncMock(return_value='ok')
    result = await reprapfirmware.send_gcode('G28', no_reply=False)
    assert result == 'ok'


@pytest.mark.asyncio
async def test_unified_download(reprapfirmware, mock_session):

    async def chunks(size):
        for item in [b'chunk1', b'chunk2']:
            yield item

    mock_session.get.return_value.__aenter__.return_value.content.iter_chunked = chunks
    downloaded = []
    async for chunk in reprapfirmware.download('test.txt'):
        downloaded.append(chunk)
    assert downloaded == [b'chunk1', b'chunk2']


@pytest.mark.asyncio
async def test_unified_upload_stream_success(reprapfirmware, mock_session):
    file = MagicMock()
    file.tell.return_value = 10
    file.read.side_effect = [b'chunk1', b'chunk2', b'']
    mock_session.reset_mock()
    mock_session.post.return_value.__aenter__.return_value.json = AsyncMock(return_value={'err': 0})
    await reprapfirmware.upload_stream('test.txt', file)


@pytest.mark.asyncio
async def test_unified_upload_stream_failure(reprapfirmware, mock_session):
    file = MagicMock()
    file.tell.return_value = 10
    file.read.side_effect = [b'chunk1', b'chunk2', b'']
    mock_session.reset_mock()
    mock_session.post.return_value.__aenter__.return_value.json = AsyncMock(return_value={'err': 1})
    with pytest.raises(IOError):
        await reprapfirmware.upload_stream('test.txt', file)


@pytest.mark.asyncio
async def test_unified_delete(reprapfirmware, mock_session):
    await reprapfirmware.delete('test.txt')
    mock_session.get.assert_called_once_with('http://10.42.0.2/rr_delete', params={'name': 'test.txt'})


@pytest.mark.asyncio
async def test_unified_fileinfo(reprapfirmware, mock_session):
    response = await reprapfirmware.fileinfo('test.txt')
    assert response == {'err': 0}
    mock_session.get.assert_called_once_with('http://10.42.0.2/rr_fileinfo', params={'name': 'test.txt'})


@pytest.mark.asyncio
async def test_unified_fileinfo_not_found(reprapfirmware, mock_session):
    mock_session.get.return_value.__aenter__.return_value.json = AsyncMock(return_value={'err': 1})
    with pytest.raises(FileNotFoundError, match='File not found: missing.gcode'):
        await reprapfirmware.fileinfo('missing.gcode')


@pytest.mark.asyncio
async def test_unified_filelist(reprapfirmware, mock_session):
    response = await reprapfirmware.filelist('/path/to/directory')
    assert response == {'err': 0}
    mock_session.get.assert_called_once_with('http://10.42.0.2/rr_filelist', params={'dir': '/path/to/directory'})


@pytest.mark.asyncio
async def test_unified_mkdir(reprapfirmware, mock_session):
    await reprapfirmware.mkdir('/path/to/directory')
    mock_session.get.assert_called_once_with('http://10.42.0.2/rr_mkdir', params={'dir': '/path/to/directory'})


@pytest.mark.asyncio
async def test_unified_move(reprapfirmware, mock_session):
    await reprapfirmware.move('old.txt', 'new.txt', overwrite=True)
    mock_session.get.assert_called_once_with(
        'http://10.42.0.2/rr_move',
        params={'old': 'old.txt', 'new': 'new.txt', 'deleteexisting': 'yes'},
    )


@pytest.mark.asyncio
async def test_reconnect_raises_on_auth_failure(mock_session):
    mock_session.get.return_value.__aenter__.return_value.json = AsyncMock(
        return_value={'err': 1},
    )
    rrf = RepRapFirmware(session=mock_session)
    with pytest.raises(aiohttp.ClientResponseError, match='Authentication failed'):
        await rrf.reconnect()


def _response_error(status):
    return aiohttp.ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=status,
        message='Error',
    )


@pytest.mark.asyncio
async def test_http_503_drains_reply_buffer(reprapfirmware):
    """Verify RRF 503 callback drains the reply buffer exactly once."""
    reprapfirmware._fetch_reply = AsyncMock(return_value='M122 diagnostic output')

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr('asyncio.sleep', AsyncMock())
        await reprapfirmware._default_http_503_busy_callback(_response_error(503))

    # A single, undecorated request: no retry loop nested inside the retry loop
    # that is already running around the failed request.
    reprapfirmware._fetch_reply.assert_awaited_once_with()
    assert reprapfirmware._last_reply == 'M122 diagnostic output'


@pytest.mark.asyncio
async def test_http_503_drain_failure_is_swallowed(reprapfirmware):
    """A 503 while draining must not escape the callback."""
    reprapfirmware._fetch_reply = AsyncMock(side_effect=_response_error(503))

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr('asyncio.sleep', AsyncMock())
        await reprapfirmware._default_http_503_busy_callback(_response_error(503))

    reprapfirmware._fetch_reply.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_503_retry_drains_without_deadlock(reprapfirmware, mock_session):
    """A real 503 must drain and retry without blocking on its own semaphore."""
    attempts = 0
    real_aenter = mock_session.get.return_value.__aenter__

    async def failing_once(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise _response_error(503)
        return await real_aenter(*args, **kwargs)

    mock_session.get.return_value.__aenter__ = failing_once

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr('asyncio.sleep', AsyncMock())
        response = await asyncio.wait_for(reprapfirmware.rr_model(key='state'), timeout=5)

    assert response == {'err': 0}
    # first attempt (503) -> drain via rr_reply -> successful retry
    assert attempts == 3


@pytest.mark.asyncio
async def test_busy_backoff_grows_and_resets(reprapfirmware, mock_session):
    """Busy backoff escalates while the board stays busy and resets on success."""
    delays = [reprapfirmware._busy_backoff_delay() for _ in range(6)]

    assert delays == [5, 10, 20, 30, 30, 30]

    await reprapfirmware.rr_model(key='state')

    assert reprapfirmware._busy_backoff_delay() == 5


@pytest.mark.asyncio
async def test_requests_are_serialized(reprapfirmware, mock_session):
    """Only one non-streaming request may be in flight against the board."""
    in_flight = 0
    peak = 0

    original_aenter = mock_session.get.return_value.__aenter__

    async def tracked_aenter(*args, **kwargs):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0)
        result = await original_aenter(*args, **kwargs)
        in_flight -= 1
        return result

    mock_session.get.return_value.__aenter__ = tracked_aenter

    await asyncio.gather(*(reprapfirmware.rr_model(key=f'k{i}') for i in range(5)))

    assert peak == 1


@pytest.mark.asyncio
async def test_close_releases_duet_session(reprapfirmware, mock_session):
    """close() hands the board's session slot back via rr_disconnect."""
    await reprapfirmware.reconnect()
    mock_session.headers = {'X-Session-Key': '4711'}
    mock_session.get.reset_mock()

    await reprapfirmware.close()

    assert mock_session.get.call_args[0][0] == 'http://10.42.0.2/rr_disconnect'
    mock_session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_without_session_key_skips_disconnect(reprapfirmware, mock_session):
    """Without a session key there is nothing to release."""
    mock_session.headers = {}

    await reprapfirmware.close()

    mock_session.get.assert_not_called()
    mock_session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_survives_failing_disconnect(reprapfirmware, mock_session):
    """A failing rr_disconnect must not prevent the session teardown."""
    mock_session.headers = {'X-Session-Key': '4711'}
    mock_session.get.side_effect = aiohttp.ClientConnectionError('boom')

    await reprapfirmware.close()

    mock_session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_reconnect_releases_previous_session(reprapfirmware, mock_session):
    """A reconnect on a live session frees the old slot before taking a new one."""
    mock_session.headers = {'X-Session-Key': '4711'}

    await reprapfirmware.reconnect()

    called = [call[0][0] for call in mock_session.get.call_args_list]
    assert called == [
        'http://10.42.0.2/rr_disconnect',
        'http://10.42.0.2/rr_connect',
    ]