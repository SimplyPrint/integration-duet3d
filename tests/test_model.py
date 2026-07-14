"""Tests for DuetPrinterModel object model fetching with include/exclude filtering."""

import copy
from unittest.mock import AsyncMock

import pytest

from simplyprint_duet3d.duet.api import RepRapFirmware
from simplyprint_duet3d.duet.model import DuetPrinterModel
from simplyprint_duet3d.duet.om_filter import ObjectModelFilter

FULL_OM = {
    "boards": [
        {
            "uniqueId": "ABC-123",
            "firmwareName": "RepRapFirmware for Duet 3 MB6HC",
            "firmwareVersion": "3.6.3",
            "vIn": {"current": 24.1},
        },
    ],
    "fans": [{"actualValue": 0.5, "requestedValue": 0.5}],
    "global": {"zSize": 610, "ScanningProbeResult": 0},
    "heat": {
        "bedHeaters": [0],
        "coldExtrudeTemperature": 160,
        "heaters": [
            {"current": 55.0, "active": 60.0, "state": "active"},
            {"current": 210.0, "active": 215.0, "state": "active"},
        ],
    },
    "job": {
        "file": {"fileName": "0:/gcodes/test.gcode", "filament": [100.0]},
        "rawExtrusion": 50.0,
        "timesLeft": {"slicer": 1000, "filament": None, "file": 900},
        "duration": 120,
        "layer": 3,
    },
    "move": {
        "axes": [{"machinePosition": 0.0}],
        "compensation": {
            "file": "0:/sys/heightmap.csv",
            "liveGrid": {"radius": -1, "mins": [0, 0], "maxs": [10, 10]},
        },
    },
    "network": {
        "name": "printer-1",
        "interfaces": [{"actualIP": "192.168.1.5"}],
    },
    "sensors": {
        "analog": [{"lastReading": 20.0}],
        "filamentMonitors": [{"enableMode": 1, "status": "ok"}],
    },
    "seqs": {
        "boards": 1,
        "fans": 2,
        "global": 3,
        "heat": 4,
        "job": 5,
        "move": 6,
        "network": 7,
        "reply": 0,
        "sensors": 8,
        "state": 9,
        "tools": 10,
        "volumes": 11,
    },
    "state": {"status": "idle", "upTime": 100, "messageBox": None},
    "tools": [{"heaters": [1], "name": "Hotend"}],
    "volumes": [{"capacity": 100}],
}

FREQUENT_OM = {
    "heat": {
        "heaters": [
            {"current": 56.0},
            {"current": 211.0},
        ],
    },
    "job": {"rawExtrusion": 51.0, "duration": 121},
    "sensors": {"filamentMonitors": [{"status": "ok"}]},
    "state": {"status": "processing", "upTime": 101},
    "fans": [{"actualValue": 0.7}],
    "seqs": dict(FULL_OM["seqs"]),
}


def truncate(value, depth):
    """Mimic M409 depth truncation: containers below the limit become {} / []."""
    if isinstance(value, dict):
        if depth <= 0:
            return {}
        return {k: truncate(v, depth - 1) for k, v in value.items()}
    if isinstance(value, list):
        if depth <= 0:
            return []
        return [truncate(v, depth - 1) for v in value]
    return value


def make_rr_model(om, frequent_om=None):
    """Fake rr_model implementing key navigation and depth truncation."""
    calls = []

    async def rr_model(
        key="",
        depth=99,
        frequently=False,
        include_null=True,
        verbose=True,
        array=None,
        **kwargs,
    ):
        calls.append({"key": key or "", "depth": depth, "frequently": frequently})
        source = frequent_om if (frequently and frequent_om is not None) else om
        node = source
        if key:
            for part in key.split("."):
                node = node[part]
        return {"key": key or "", "result": truncate(node, depth)}

    return rr_model, calls


def make_model(om, frequent_om=None, sbc=False, **kwargs):
    """Make model."""
    model = DuetPrinterModel(api=RepRapFirmware(), sbc=sbc, **kwargs)
    rr_model, calls = make_rr_model(om, frequent_om)
    model.api.rr_model = rr_model
    model.api.rr_reply = AsyncMock(return_value="")
    return model, calls


def requested_keys(calls):
    """Return the set of requested rr_model keys."""
    return {call["key"] for call in calls}


@pytest.mark.asyncio
async def test_initialize_standalone_fetches_only_included_paths():
    """Initialize standalone fetches only included paths."""
    om = copy.deepcopy(FULL_OM)
    model, calls = make_model(om)

    await model._initialize_object_model()

    # unread top-level keys are neither fetched nor stored
    keys = requested_keys(calls)
    for unread in ("fans", "global", "volumes"):
        assert unread not in model.om
        assert not any(key.startswith(unread) for key in keys)

    # sibling branches inside included trees are not fetched either
    assert not any(key.startswith("move.axes") for key in keys)
    assert not any(key.startswith("network.interfaces") for key in keys)

    assert model.om["network"] == {"name": "printer-1"}
    assert model.om["move"] == {"compensation": FULL_OM["move"]["compensation"]}
    assert model.om["state"] == {"status": "idle"}
    assert model.om["heat"] == FULL_OM["heat"]
    assert model.om["tools"] == FULL_OM["tools"]
    assert model.om["boards"] == FULL_OM["boards"]
    assert model.om["sensors"] == {"filamentMonitors": FULL_OM["sensors"]["filamentMonitors"]}


@pytest.mark.asyncio
async def test_initialize_standalone_does_not_refetch_plain_values():
    """Initialize standalone does not refetch plain values."""
    om = copy.deepcopy(FULL_OM)
    model, calls = make_model(om)

    await model._initialize_object_model()

    # plain values are complete in the parent response; only containers warrant requests
    keys = requested_keys(calls)
    assert "network.name" not in keys
    assert "heat.coldExtrudeTemperature" not in keys
    assert not any(key.startswith("seqs.") for key in keys)


@pytest.mark.asyncio
async def test_initialize_seeds_seqs():
    """Initialize seeds seqs."""
    om = copy.deepcopy(FULL_OM)
    model, calls = make_model(om)

    await model._initialize_object_model()

    assert model.seqs == FULL_OM["seqs"]

    # a subsequent poll with unchanged seqs refetches nothing
    calls.clear()
    model2_frequent = copy.deepcopy(FREQUENT_OM)
    rr_model, poll_calls = make_rr_model(om, model2_frequent)
    model.api.rr_model = rr_model
    await model._update_object_model()
    keys = requested_keys(poll_calls)
    assert "boards" not in keys
    assert "tools" not in keys


@pytest.mark.asyncio
async def test_initialize_sbc_fetches_each_included_key_once():
    """Initialize sbc fetches each included key once."""
    om = copy.deepcopy(FULL_OM)
    model, calls = make_model(om, sbc=True)

    await model._initialize_object_model()

    keys = requested_keys(calls)
    assert keys == {"", "boards", "heat", "job", "move", "network", "sensors", "seqs", "state", "tools"}
    # deep single-shot responses are pruned to the included subtrees
    assert model.om["move"] == {"compensation": FULL_OM["move"]["compensation"]}
    assert model.om["network"] == {"name": "printer-1"}
    assert model.om["state"] == {"status": "idle"}


@pytest.mark.asyncio
async def test_narrow_poll_requests_only_frequent_paths():
    """Narrow poll requests only frequent paths."""
    om = copy.deepcopy(FULL_OM)
    model, _ = make_model(om, frequent_om=copy.deepcopy(FREQUENT_OM))
    await model._initialize_object_model()

    rr_model, poll_calls = make_rr_model(om, copy.deepcopy(FREQUENT_OM))
    model.api.rr_model = rr_model
    await model._update_object_model()

    keys = requested_keys(poll_calls)
    assert keys == {"seqs", "heat", "job", "sensors.filamentMonitors", "state"}
    # never the whole-model poll
    assert "" not in keys

    # live values are merged while non-frequent data is preserved
    assert model.om["heat"]["heaters"][0]["current"] == 56.0
    assert model.om["heat"]["heaters"][0]["active"] == 60.0
    assert model.om["heat"]["bedHeaters"] == [0]
    assert model.om["job"]["rawExtrusion"] == 51.0
    assert model.om["job"]["file"]["fileName"] == "0:/gcodes/test.gcode"
    assert model.om["state"] == {"status": "processing"}
    assert model.om["sensors"]["filamentMonitors"][0]["enableMode"] == 1


@pytest.mark.asyncio
async def test_narrow_poll_seq_change_refetches_included_subtree_only():
    """Narrow poll seq change refetches included subtree only."""
    om = copy.deepcopy(FULL_OM)
    model, _ = make_model(om, frequent_om=copy.deepcopy(FREQUENT_OM))
    await model._initialize_object_model()

    om["seqs"] = dict(om["seqs"], move=7, fans=3, volumes=12)
    om["seqs"]["global"] = 4
    om["move"]["compensation"]["file"] = "0:/sys/heightmap2.csv"
    frequent = copy.deepcopy(FREQUENT_OM)
    frequent["seqs"] = dict(om["seqs"])
    rr_model, poll_calls = make_rr_model(om, frequent)
    model.api.rr_model = rr_model

    await model._update_object_model()

    keys = requested_keys(poll_calls)
    assert "move.compensation" in keys
    assert not any(key.startswith("fans") for key in keys)
    assert not any(key.startswith("global") for key in keys)
    assert not any(key.startswith("volumes") for key in keys)
    assert not any(key == "move" for key in keys)
    assert model.om["move"]["compensation"]["file"] == "0:/sys/heightmap2.csv"


@pytest.mark.asyncio
async def test_narrow_poll_reply_seq_fetches_reply():
    """Narrow poll reply seq fetches reply."""
    om = copy.deepcopy(FULL_OM)
    model, _ = make_model(om, frequent_om=copy.deepcopy(FREQUENT_OM))
    await model._initialize_object_model()

    om["seqs"] = dict(om["seqs"], reply=1)
    frequent = copy.deepcopy(FREQUENT_OM)
    frequent["seqs"] = dict(om["seqs"])
    rr_model, _ = make_rr_model(om, frequent)
    model.api.rr_model = rr_model
    model.api.rr_reply = AsyncMock(return_value="ok")

    await model._update_object_model()

    assert model._reply == "ok"
    assert model._wait_for_reply.is_set()


@pytest.mark.asyncio
async def test_unfiltered_model_uses_whole_model_poll():
    """Unfiltered model uses whole model poll."""
    om = copy.deepcopy(FULL_OM)
    frequent = copy.deepcopy(FREQUENT_OM)
    model, calls = make_model(om, frequent_om=frequent, om_filter=ObjectModelFilter())
    await model._initialize_object_model()

    assert "fans" in model.om
    assert "global" in model.om

    model.seqs = dict(om["seqs"])
    rr_model, poll_calls = make_rr_model(om, frequent)
    model.api.rr_model = rr_model
    await model._update_object_model()

    assert requested_keys(poll_calls) == {""}
    assert model.om["fans"][0]["actualValue"] == 0.7
