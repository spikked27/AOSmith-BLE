"""Verify real DR transitions and attempt one durable, bounded clock correction."""

import json
from collections import deque
from datetime import datetime
from pathlib import Path

from bleak.exc import BleakError
from homeassistant.components import persistent_notification
from homeassistant.helpers.storage import Store

from .const import CONF_AUTO_CLOCK, DOMAIN
from .protocol import ProtocolError
from .schedule import build_schedule
from .timing import DR_NAMES, decode_dr, schedule_digest, tariff_timing

GRACE_SECONDS = 180
PRE_WINDOW = 300
MAX_GAP = 90
CONFIRM_SPAN = 60
CHECK_WINDOW = 600
CORRECTION_INTERVAL = 86400


def _saved_attempt(path):
    data = json.loads(Path(path).read_text())["data"]
    return data.get("last_auto_attempt_at"), data.get("correction_attempted")


def gate_reason(state):
    """Only the observed Hybrid profile is eligible for automatic clock repair."""
    if state.mode != 4:
        return "Clock verification requires Hybrid mode"
    if state.fault & 0xFF not in (0, 42):
        return "Heater fault active"
    flags = ("utility_override", "cta_present", "utility_enrollment", "advanced_load")
    if any(key not in state.registers for key in flags):
        return "Utility status unavailable"
    if any(state.registers[key] for key in flags):
        return "Utility control or override active"
    if decode_dr(state.registers.get("dr_status")) is None:
        return "DR status unavailable or unsupported"
    return None


class ClockGuard:
    def __init__(self, hass, coordinator):
        self.hass = hass
        self.coordinator = coordinator
        self.store = Store(hass, 1, f"{DOMAIN}.{coordinator.entry.entry_id}.clock_guard")
        self.data = {"status": "Waiting for transition", "desync_active": False, "desync_count": 0}
        self.loaded = False
        self.samples = deque(maxlen=60)
        self.pending = None
        self.context = None
        self.handled = None
        self.schedule_key = None
        self.schedule = None

    @property
    def automatic(self):
        return self.coordinator.options.get(CONF_AUTO_CLOCK, True)

    async def async_load(self):
        if self.loaded:
            return
        saved = await self.store.async_load()
        if isinstance(saved, dict):
            self.data.update(saved)
        self.data["status"] = (
            "Clock desync detected" if self.data["desync_active"] else "Waiting for transition"
        )
        self.loaded = True

    def reset_observations(self, reason="Waiting for transition"):
        self.samples.clear()
        self.pending = None
        self.data.update(status=reason, reason=reason)

    def unavailable(self, reason="Heater unavailable"):
        self.reset_observations("Check unavailable")
        self.data["reason"] = reason

    async def _schedule(self):
        state = self.coordinator.tariff_state or {}
        operation = state.get("last_operation", {})
        if (
            state.get("schedule_incomplete")
            or operation.get("outcome") != "readback_confirmed"
            or operation.get("restoring")
            or not state.get("applied_plan")
        ):
            return None
        key = (state.get("applied_at"), state.get("applied_preference"))
        if key != self.schedule_key:
            self.schedule = state.get("applied_schedule") or await self.hass.async_add_executor_job(
                build_schedule, state["applied_plan"], state["applied_preference"]
            )
            self.schedule_key = key
        return self.schedule

    async def async_observe(self, state):
        """Called only under the coordinator's command lock, after a fresh poll."""
        await self.async_load()
        self.data["automatic_correction_enabled"] = self.automatic
        schedule = await self._schedule()
        if schedule is None:
            self.reset_observations("No verified tariff")
            return
        now = self.coordinator.local_now()
        observed = state.register_read_at.get("dr_status")
        if observed:
            observed = datetime.fromisoformat(observed).astimezone(now.tzinfo)
        if observed is None or not 0 <= (now - observed).total_seconds() <= MAX_GAP:
            self.unavailable("Fresh DR timestamp unavailable")
            return
        now = observed
        stamp = now.timestamp()
        timing = tariff_timing(schedule, now)
        reason = timing.get("reason") or gate_reason(state)
        if state.registers.get("energy_preference_experimental") != schedule["extra"]["words"][25]:
            reason = "Savings preference differs from confirmed tariff"
        if reason:
            self.reset_observations("Verification paused")
            self.data["reason"] = reason
            return
        context = (
            schedule_digest(schedule),
            str(now.tzinfo),
            now.utcoffset().total_seconds(),
            state.mode,
            state.target_temperature,
        )
        if context != self.context or (self.samples and not 0 < stamp - self.samples[-1][0] <= MAX_GAP):
            self.reset_observations()
            self.context = context
        actual = decode_dr(state.registers["dr_status"])
        transition = timing["transition"]
        boundary = transition["at"].timestamp()
        key = transition["at"].isoformat()
        if self.pending is not None and self.pending["key"] != key:
            self.pending = None
        self.data.update(
            observed_dr=DR_NAMES[actual],
            observed_raw=state.registers["dr_status"],
            expected_dr=DR_NAMES[timing["expected"]],
            last_observed_at=now.isoformat(),
            next_transition_at=timing["next"]["at"].isoformat(),
        )
        if self.handled == key:
            self.samples.append((stamp, actual))
            return
        pre = [(at, value) for at, value in self.samples if boundary - PRE_WINDOW <= at < boundary]
        if self.pending is None and 0 <= stamp - boundary <= CHECK_WINDOW:
            if len(pre) >= 2 and all(value == transition["before"] for _, value in pre[-2:]):
                self.pending = {"key": key, "boundary": boundary, "before": transition["before"], "bad": []}
            elif stamp - boundary > GRACE_SECONDS:
                self.data.update(status="Waiting for transition", reason="No fresh pre-transition evidence")
        self.samples.append((stamp, actual))
        if self.pending is None or self.pending["key"] != key:
            return
        age = stamp - boundary
        if age > CHECK_WINDOW or timing["next"]["at"].timestamp() - boundary <= CHECK_WINDOW:
            self.pending = None
            self.handled = key
            self.data.update(status="Check unavailable", reason="Transition window ambiguous or expired")
            return
        if actual == transition["after"]:
            self.handled = key
            self.pending = None
            if age <= GRACE_SECONDS:
                self.data.update(
                    status="In sync",
                    reason="Observed tariff transition on time",
                    last_verified_at=now.isoformat(),
                    last_verified_transition=key,
                    verification_tolerance_seconds=GRACE_SECONDS,
                )
                if self.data["desync_active"]:
                    self.data.update(
                        desync_active=False, correction_attempted=False, resolved_at=now.isoformat()
                    )
                    self._notify(
                        "Clock timing verified by a later tariff transition. The desync event remains in history."
                    )
            else:
                self.data.update(
                    status="Late transition observed", reason="Transition arrived after the grace period"
                )
            await self.store.async_save(self.data)
            return
        if age < GRACE_SECONDS:
            self.data.update(status="Checking transition", reason="Waiting through transition grace period")
            return
        if actual != transition["before"]:
            self.pending = None
            self.handled = key
            self.data.update(status="Check unavailable", reason="Unexpected DR value; no clock correction")
            return
        self.pending["bad"].append(stamp)
        bad = self.pending["bad"]
        if len(bad) < 3 or bad[-1] - bad[0] < CONFIRM_SPAN:
            self.data.update(
                status="Checking transition", reason="Confirming missed transition with fresh reads"
            )
            return
        self.handled = key
        self.pending = None
        if not self.data["desync_active"]:
            self.data["desync_count"] += 1
            self.data["correction_attempted"] = False
            self._notify(
                "Clock desync detected: the expected tariff transition was missed. Checking the saved schedule before correction."
            )
        self.data.update(
            status="Clock desync detected",
            desync_active=True,
            last_desync_at=now.isoformat(),
            missed_transition_at=key,
            reason="DR stayed at the previous level after repeated fresh reads",
        )
        await self.store.async_save(self.data)
        if not self.automatic:
            self.data["reason"] = "Automatic correction is disabled"
            await self.store.async_save(self.data)
            return
        if self.data.get("correction_attempted"):
            self.data.update(
                status="Manual attention required", reason="A correction was already attempted; no repeat"
            )
            await self.store.async_save(self.data)
            return
        previous = self.data.get("last_auto_attempt_at")
        if previous:
            age = stamp - datetime.fromisoformat(previous).timestamp()
            if not CORRECTION_INTERVAL <= age:
                self.data["reason"] = "Automatic correction is limited to once per 24 hours"
                await self.store.async_save(self.data)
                return
        await self._correct(schedule, context, transition)

    async def _correct(self, schedule, context, transition):
        """Compare device tariff and reread live status before the single write."""
        coordinator = self.coordinator
        try:
            captured = await coordinator.client.inspect_schedule()
            if not captured.get("complete") or schedule_digest(captured) != context[0]:
                self.data.update(
                    status="Schedule mismatch", reason="Device tariff does not match; clock left unchanged"
                )
                return
            fresh = await coordinator.client.read_state()
            now = coordinator.local_now()
            timing = tariff_timing(schedule, now)
            reason = gate_reason(fresh) or timing.get("reason")
            if (
                reason
                or timing["transition"]["at"] != transition["at"]
                or now.timestamp() - transition["at"].timestamp() > CHECK_WINDOW
                or str(now.tzinfo) != context[1]
                or now.utcoffset().total_seconds() != context[2]
                or fresh.target_temperature != context[4]
                or fresh.registers.get("energy_preference_experimental") != schedule["extra"]["words"][25]
            ):
                self.data.update(
                    status="Check unavailable", reason=reason or "Conditions changed before correction"
                )
                return
            if decode_dr(fresh.registers["dr_status"]) != transition["before"]:
                self.data.update(
                    status="Late transition observed",
                    reason="Status changed before correction; no write sent",
                )
                return
            self.data.update(
                last_auto_attempt_at=now.isoformat(),
                correction_attempted=True,
                status="Correcting clock",
                reason="Confirmed schedule and missed DR transition",
            )
            await self.store.async_save(self.data)
            saved = await self.hass.async_add_executor_job(_saved_attempt, self.store.path)
            if saved != (self.data["last_auto_attempt_at"], True):
                raise OSError("Could not persist clock correction limit")
            previous = coordinator.client.clock_operation
            try:
                result = await coordinator.client.set_clock(coordinator.local_now)
            finally:
                if coordinator.client.clock_operation is not previous:
                    await coordinator.clock.async_record_operation(
                        coordinator.client.clock_operation, reason="missed_tariff_transition"
                    )
            self.data.update(
                status="Clock set; awaiting verification",
                last_correction_outcome=result["outcome"],
                reason="Write accepted; a later transition must verify timing",
            )
            self._notify(
                "Clock desync detected and one clock correction sent. Waiting for a later tariff transition to verify timing."
            )
        except (BleakError, TimeoutError, ProtocolError, OSError, ValueError, KeyError) as err:
            self.data.update(status="Correction failed", reason=type(err).__name__)
            self._notify(
                "Clock desync detected, but automatic correction could not complete. Check Clock synchronization status."
            )
        finally:
            self.samples.clear()
            await self.store.async_save(self.data)

    def _notify(self, message):
        persistent_notification.async_create(
            self.hass,
            message,
            title="AO Smith clock synchronization",
            notification_id=f"{DOMAIN}_{self.coordinator.entry.entry_id}_clock",
        )
