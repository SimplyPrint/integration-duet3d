"""Duet Printer model class."""

import asyncio
import csv
import io
import logging
from enum import auto

import aiohttp

import attr
from attr import define, field

from pyee.asyncio import AsyncIOEventEmitter

from strenum import CamelCaseStrEnum, StrEnum

from .api import RepRapFirmware
from .om_filter import ObjectModelFilter

#: Object model paths the connector reads. Anything outside these subtrees is
#: never requested from the printer. Defaults match the Proteor machines.
DEFAULT_OM_INCLUDE_PATHS = (
    "boards",
    "heat",
    "job",
    "move.compensation",
    "network.name",
    "sensors.filamentMonitors",
    "state.status",
    "tools",
)

#: Paths the model itself needs to operate; always added to a custom include.
REQUIRED_OM_PATHS = (
    "seqs",
    "state.status",
)

#: Subtrees polled with the M409 "frequently" flag on every tick. Everything
#: else only refreshes when its seq counter changes. Keep this to the live
#: values the connector forwards (temperatures, job progress, runout, status).
DEFAULT_OM_FREQUENT_PATHS = (
    "heat",
    "job",
    "sensors.filamentMonitors",
    "state",
)


def merge_dictionary(source, destination):
    """Merge multiple dictionaries."""
    result = {}
    try:
        destination_dict = dict(destination)
    except TypeError:
        return None

    for key, value in source.items():
        if isinstance(value, dict):
            result[key] = merge_dictionary(value, destination.get(key, {}))
        elif isinstance(value, list):
            result[key] = value
            dest_value = destination.get(key, [])
            if len(dest_value) == 0:
                continue
            if len(value) > len(dest_value):
                raise ValueError(
                    f"List length mismatch in merge for key: {key} src: {value} dest: {dest_value}",
                )
            for idx, item in enumerate(value):
                if dest_value[idx] is not None and isinstance(item, dict):
                    result[key][idx] = merge_dictionary(item, dest_value[idx])
        else:
            result[key] = destination.get(key, value)
        destination_dict.pop(key, None)
    result.update(destination_dict)
    return result


class DuetModelEvents(StrEnum):
    """Duet Model Events enum."""

    state = auto()
    objectmodel = auto()
    connect = auto()
    close = auto()


class DuetState(CamelCaseStrEnum):
    """Duet State enum."""

    disconnected = auto()
    starting = auto()
    updating = auto()
    off = auto()
    halted = auto()
    pausing = auto()
    paused = auto()
    resuming = auto()
    cancelling = auto()
    processing = auto()
    simulating = auto()
    busy = auto()
    changing_tool = auto()
    idle = auto()


@define
class DuetPrinterModel:
    """Duet Printer model class."""

    api = field(type=RepRapFirmware, factory=RepRapFirmware)
    om = field(type=dict, default=None)
    seqs = field(type=dict, factory=dict)
    logger = field(type=logging.Logger, factory=logging.getLogger)
    events = field(type=AsyncIOEventEmitter, factory=AsyncIOEventEmitter)
    sbc = field(type=bool, default=False)
    om_filter = field(
        type=ObjectModelFilter,
        factory=lambda: ObjectModelFilter(include=DEFAULT_OM_INCLUDE_PATHS),
    )
    om_frequent_paths = field(type=tuple, default=DEFAULT_OM_FREQUENT_PATHS, converter=tuple)
    _reply = field(type=str, default=None)
    _wait_for_reply = field(type=asyncio.Event, factory=asyncio.Event)

    def __attrs_post_init__(self) -> None:
        """Post init."""
        self.api.callbacks[503] = self._http_503_callback
        self.events.on(DuetModelEvents.objectmodel, self._track_state)
        if self.om_filter.include is not None:
            self.om_filter = attr.evolve(
                self.om_filter,
                include=self.om_filter.include + REQUIRED_OM_PATHS,
            )

    @property
    def state(self) -> DuetState:
        """Get the state of the printer."""
        try:
            return DuetState(self.om["state"]["status"])
        except (KeyError, TypeError):
            return DuetState.disconnected

    async def _track_state(self, old_om: dict):
        """Track the state of the printer."""
        if old_om is None:
            return
        old_state = DuetState(old_om["state"]["status"])
        if self.state != old_state:
            self.logger.debug(f"State change: {old_state} -> {self.state}")
            self.events.emit(DuetModelEvents.state, old_state)

    async def connect(self) -> None:
        """Connect the printer."""
        result = await self.api.connect()
        if "isEmulated" in result:
            self.sbc = True
        result = await self._fetch_full_status()
        self.om = result["result"]
        self._seed_seqs()
        self.events.emit(DuetModelEvents.connect)

    async def close(self) -> None:
        """Close the printer."""
        await self.api.close()
        self.events.emit(DuetModelEvents.close)

    def connected(self) -> bool:
        """Check if the printer is connected."""
        if self.api.session is None or self.api.session.closed:
            return False
        return True

    async def gcode(self, command: str, no_reply: bool = True) -> str:
        """Send a GCode command to the printer."""
        self.logger.debug(f"Sending GCode: {command}")
        self._wait_for_reply.clear()
        await self.api.rr_gcode(
            gcode=command,
            no_reply=True,
        )
        if no_reply:
            return ""
        return await self.reply()

    async def heightmap(self) -> dict:
        """Get the heightmap from the printer."""
        compensation = self.om["move"]["compensation"]
        heightmap = io.BytesIO()

        async for chunk in self.api.rr_download(filepath=compensation["file"]):
            heightmap.write(chunk)

        heightmap.seek(0)
        heightmap = heightmap.read().decode("utf-8")

        self.logger.debug("Mesh data: {!s}".format(heightmap))

        mesh_data_csv = csv.reader(heightmap.splitlines()[3:], dialect="unix")

        mesh_data = []
        z_min, z_max = float("inf"), float("-inf")

        for row in mesh_data_csv:
            x_line = [float(x.strip()) for x in row]
            z_min = min(z_min, *x_line)
            z_max = max(z_max, *x_line)
            mesh_data.append(x_line)

        return {
            "type": "rectangular" if compensation["liveGrid"]["radius"] == -1 else "circular",
            "x_min": compensation["liveGrid"]["mins"][0],
            "x_max": compensation["liveGrid"]["maxs"][0],
            "y_min": compensation["liveGrid"]["mins"][1],
            "y_max": compensation["liveGrid"]["maxs"][1],
            "z_min": z_min,
            "z_max": z_max,
            "mesh_data": mesh_data,
        }

    async def reply(self) -> str:
        """Get the last reply from the printer."""
        await self._wait_for_reply.wait()
        return self._reply

    async def _fetch_objectmodel_recursive(
        self,
        *args,
        key="",
        depth=1,
        frequently=False,
        include_null=True,
        verbose=True,
        array=None,
        **kwargs,
    ) -> dict:
        """
        Fetch the object model recursively.

        Duet2:
        The implementation is recursive to fetch the object model in chunks.
        This is required because the object model is too large to fetch in a single request.
        The implementation might be slow because of the recursive nature of the function, but
        this helps to reduce the load on the duet board.

        Duet3 or SBC mode (isEmulated):
        The implementation is not recursive and fetches the object model in a single request
        starting from the second level of the object model (d=2).
        """
        if self.sbc and depth == 2:
            depth = 99

        response = await self.api.rr_model(
            *args,
            key=key,
            depth=depth,
            frequently=frequently,
            include_null=include_null,
            verbose=verbose,
            array=array,
            **kwargs,
        )

        if (depth == 1 or not self.sbc) and isinstance(response["result"], dict) and key != "global":
            for k, v in list(response["result"].items()):
                sub_key = f"{key}.{k}" if key else k
                if not self.om_filter.wanted(sub_key):
                    del response["result"][k]
                    continue
                if isinstance(v, dict):
                    sub_depth = depth + 1
                elif isinstance(v, list):
                    sub_depth = 99
                else:
                    # plain values are complete at any depth - no refetch needed
                    continue
                sub_response = await self._fetch_objectmodel_recursive(
                    *args,
                    key=sub_key,
                    depth=sub_depth,
                    frequently=frequently,
                    include_null=include_null,
                    verbose=verbose,
                    **kwargs,
                )
                sub_result = sub_response["result"]
                if isinstance(sub_result, dict):
                    # SBC responses arrive as one deep subtree - prune what the
                    # recursion could not filter per-request.
                    sub_result = self.om_filter.prune(sub_result, sub_key)
                response["result"][k] = sub_result
        elif "next" in response and response["next"] > 0:
            next_data = await self._fetch_objectmodel_recursive(
                *args,
                key=key,
                depth=depth,
                frequently=frequently,
                include_null=include_null,
                verbose=verbose,
                array=response["next"],
                **kwargs,
            )
            response["result"].extend(next_data["result"])
            response["next"] = 0

        return response

    async def _fetch_full_status(self) -> dict:
        try:
            response = await self._fetch_objectmodel_recursive(
                key="",
                depth=1,
                frequently=False,
                include_null=True,
                verbose=True,
            )
        except KeyError:
            response = {}

        return response

    async def _handle_om_changes(self, changes: dict) -> None:
        """Handle object model changes."""
        if "reply" in changes:
            self._reply = await self.api.rr_reply()
            self._wait_for_reply.set()
            self.logger.debug(f"Reply: {self._reply}")
            changes.pop("reply")

        if "volChanges" in changes:
            # TODO: handle volume changes
            changes.pop("volChanges")

        for key in changes:
            for path in self.om_filter.refetch_paths(key):
                changed_obj = await self._fetch_objectmodel_recursive(
                    key=path,
                    depth=2,
                    frequently=False,
                    include_null=True,
                    verbose=True,
                )
                value = changed_obj["result"]
                if isinstance(value, dict):
                    value = self.om_filter.prune(value, path)
                self._set_om_value(path, value)

    def _set_om_value(self, path: str, value) -> None:
        """Set a value in the object model by dotted path, creating parent nodes."""
        node = self.om
        parts = path.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value

    def _merge_om_value(self, path: str, value) -> None:
        """Merge a partial subtree into the object model at a dotted path."""
        wrapped = value
        for part in reversed(path.split(".")):
            wrapped = {part: wrapped}
        self.om = merge_dictionary(self.om, wrapped)

    def _seed_seqs(self) -> None:
        """Seed the seq counters from a full fetch so the next poll only refetches real changes."""
        seqs = self.om.get("seqs") if isinstance(self.om, dict) else None
        if isinstance(seqs, dict):
            self.seqs = dict(seqs)

    async def tick(self) -> None:
        """Tick the printer."""
        if not self.connected():
            await self.connect()

        if self.om is None:
            await self._initialize_object_model()
        else:
            await self._update_object_model()

    async def _initialize_object_model(self) -> None:
        """Initialize the object model by fetching the full status."""
        result = await self._fetch_full_status()
        if result is None or "result" not in result:
            return
        self.om = result["result"]
        self._seed_seqs()
        self.events.emit(DuetModelEvents.objectmodel, None)

    async def _update_object_model(self) -> None:
        """Update the object model by fetching partial updates."""
        if self.om_filter.include is None:
            await self._update_object_model_full()
        else:
            await self._update_object_model_narrow()

    async def _update_object_model_full(self) -> None:
        """Update the object model with a single whole-model "frequently" poll."""
        result = await self.api.rr_model(
            key="",
            depth=99,
            frequently=True,
            include_null=True,
            verbose=True,
        )
        if result is None or "result" not in result:
            return
        changes = self._detect_om_changes(result["result"]["seqs"])
        old_om = dict(self.om)
        try:
            self.om = merge_dictionary(self.om, result["result"])
            if changes:
                await self._handle_om_changes(changes)
            self.events.emit(DuetModelEvents.objectmodel, old_om)
        except (TypeError, KeyError, ValueError):
            self.logger.exception("Failed to update object model - fetch full model")
            self.logger.debug(f"Old OM: {old_om} result {result['result']}")
            self.om = None
            # TODO: send to sentry

    async def _update_object_model_narrow(self) -> None:
        """Update the object model by polling only the live subtrees.

        A whole-model "frequently" poll makes the firmware serialize live
        values of every top-level key (in SBC mode a multi-kilobyte
        GetObjectModel transfer over SPI on every tick). Polling the seq
        counters plus the few live subtrees the connector reads keeps each
        transfer small.
        """
        seqs_response = await self.api.rr_model(
            key="seqs",
            depth=99,
            frequently=False,
            include_null=True,
            verbose=True,
        )
        if seqs_response is None or not isinstance(seqs_response.get("result"), dict):
            return
        changes = self._detect_om_changes(seqs_response["result"])
        old_om = dict(self.om)
        try:
            self._merge_om_value("seqs", seqs_response["result"])
            for path in self.om_frequent_paths:
                if not self.om_filter.wanted(path):
                    continue
                response = await self.api.rr_model(
                    key=path,
                    depth=99,
                    frequently=True,
                    include_null=True,
                    verbose=True,
                )
                if response is None or "result" not in response:
                    continue
                value = response["result"]
                if isinstance(value, dict):
                    value = self.om_filter.prune(value, path)
                self._merge_om_value(path, value)
            if changes:
                await self._handle_om_changes(changes)
            self.events.emit(DuetModelEvents.objectmodel, old_om)
        except (TypeError, KeyError, ValueError):
            self.logger.exception("Failed to update object model - fetch full model")
            self.logger.debug(f"Old OM: {old_om}")
            self.om = None
            # TODO: send to sentry

    def _detect_om_changes(self, new_seqs) -> dict:
        """Detect changes between the current and new sequences."""
        changes = {}
        for key, value in new_seqs.items():
            if key not in self.seqs or self.seqs[key] != value:
                changes[key] = value
        self.seqs = new_seqs
        return changes

    async def _http_503_callback(self, error: aiohttp.ClientResponseError):
        """503 callback."""
        if self.sbc:
            await asyncio.sleep(5)
            return

        # there are no more than 10 clients connected to the duet board
        for _ in range(10):
            reply = await self.api.rr_reply(nocache=True)
            if reply == "":
                break
            self._reply = reply
        self._wait_for_reply.set()
