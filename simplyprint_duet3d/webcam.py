"""Webcam module for the Duet SimplyPrint connector."""

from typing import Coroutine, Union

import imageio.v3 as iio

import requests

from requests_toolbelt.multipart import decoder

from simplyprint_ws_client.shared.camera.base import (
    BaseCameraProtocol,
    CameraProtocolConnectionError,
    CameraProtocolPollingMode,
)

from yarl import URL


class DuetSnapshotCamera(BaseCameraProtocol):
    """Camera protocol for capturing snapshots from Duet webcams."""

    polling_mode = CameraProtocolPollingMode.ON_DEMAND
    is_async = False

    @staticmethod
    def test(uri: URL) -> Union[bool, Coroutine[None, None, bool]]:
        """Test if the URI is supported by this camera protocol."""
        return uri.scheme in ("http", "https")

    def read(self):
        """Read an image from the webcam."""
        r = requests.get(str(self.uri))
        content_type = r.headers["Content-Type"].lower()
        raw_data = None

        if "multipart" in content_type:
            dec = decoder.MultipartDecoder.from_response(r)
            for part in dec.parts:
                if part.headers[b"Content-Type"].lower() != b"image/jpeg":
                    continue
                raw_data = part.content
                break
        else:
            raw_data = r.content

        if raw_data is None:
            raise CameraProtocolConnectionError(
                "No image data received from the camera.",
            )

        img = iio.imread(
            uri=raw_data,
            extension=".jpeg",
            index=None,
        )

        yield iio.imwrite("<bytes>", img, extension=".jpeg")
