SimplyPrint Duet3d integration
================================================

Many thanks to `Tim Schneider <https://github.com/timschneider>`_  at https://github.com/Meltingplot/duet-simplyprint-connector/ for originally creating this integration and allowing us to use it.

This package acts as a bridge between Duet-based 3D printers and the SimplyPrint.io cloud service.

It communicates with the printer using the Duet HTTP API.
For more information, visit https://github.com/Duet3D/RepRapFirmware/wiki/HTTP-requests.

Communication with SimplyPrint.io is handled via the `simplyprint-ws-client`.

------------
Status
------------

Supported features:

- Printer registration
- Printer status update
- Webcam snapshots and MJPEG livestreaming via the ``simplyprint-ws-client`` camera pool
- GCode receiving
- File downloading
- Printer control (start, pause, resume, cancel)
- Self upgrading via G-Code M997
- Device health update
- Bed leveling
- Filament sensor
- Duet auto discovery with tracking based on BoardID
- Leave a cookie on the printer to identify the printer in the future (``0:/sys/simplyprint-connector.json``)
- Grab the webcam URL from DWC settings file from the printer
- Webcam URL can be a snapshot endpoint or MJPEG stream

Missing features:

- PSU Control
- GCode Macros / Scripts [not yet implemented by SimplyPrint.io for Duet]
- GCode terminal [not yet implemented by SimplyPrint.io for Duet]
- Receive messages from Printer in SimplyPrint.io [not yet implemented by SimplyPrint.io for Duet]


------------
Installation
------------
Open an SSH session to your SimplyPrint-connected device, such as a Raspberry Pi 4B.

.. code-block:: sh

    source <(curl -sSL https://raw.githubusercontent.com/simplyprint/integration-duet3d/refs/heads/main/install.sh)


-----------------------------
Content of DuetConnector.json
-----------------------------

The default password for the Duet is `reprap`, even if the web interface does not require a login.

.. code-block:: json

    [
        {
            "id": null,
            "token": null,
            "name": null,
            "in_setup": true,
            "short_id": null,
            "public_ip": null,
            "unique_id": "...",
            "duet_uri": "http://192.168.1.0",
            "duet_password": "reprap",
            "duet_unique_id": "YOUR_DUET_BOARD_ID",
            "duet_name": "YOUR_DUET_NAME",
            "webcam_uri": "http://URI_OF_WEBCAM_SNAPSHOT_ENDPOINT/webcam",
            "duet_om_include": null,
            "duet_om_exclude": null,
            "duet_om_frequent": null,
            "duet_poll_interval": null
        }
    ]

Object model polling options (all optional, ``null`` selects the built-in
defaults):

- ``duet_om_include``: list of object model paths (e.g. ``"heat"``,
  ``"move.compensation"``) the connector is allowed to fetch. Anything outside
  these subtrees is never requested from the printer, which keeps M409 /
  ``rr_model`` traffic (and the DCS<->Duet SPI link in SBC mode) small. Use
  ``["*"]`` to disable filtering and fetch the full object model. The paths
  ``seqs`` and ``state.status`` are always fetched on top of a custom list.
- ``duet_om_exclude``: list of paths that are never fetched, wins over
  ``duet_om_include``.
- ``duet_om_frequent``: subtrees polled with the M409 "frequently" flag on
  every tick (default: ``heat``, ``job``, ``sensors.filamentMonitors``,
  ``state``). Only paths allowed by the include/exclude filter are polled.
- ``duet_poll_interval``: seconds between polls (default ``1.0``, minimum
  ``0.1``). Raise this to further reduce load on the printer.


-----------------------------------------------
Usage of Meltingplot Duet SimplyPrint Connector
-----------------------------------------------

- Create a configuration with `simplyprint-duet3d autodiscover`
- *Optional* Edit the configuration file `~/.config/SimplyPrint/DuetConnector.json`
- Start the duet simplyprint connector with `simplyprint-duet3d start` or `systemctl start simplyprint-duet3d.service`
- Add the printer via the SimplyPrint.io web interface.
