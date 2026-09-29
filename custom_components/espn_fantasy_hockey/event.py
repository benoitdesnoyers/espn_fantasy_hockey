"""League transactions as an event entity, for automations."""

from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import TRANSACTION_TYPES
from .coordinator import (
    EspnFantasyHockeyConfigEntry,
    EspnFantasyHockeyCoordinator,
    describe_transaction,
)
from .entity import EspnFantasyHockeyEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EspnFantasyHockeyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the transactions event entity."""
    async_add_entities([TransactionEvent(entry.runtime_data)])


class TransactionEvent(EspnFantasyHockeyEntity, EventEntity):
    """Fires for each new add, drop, waiver claim or trade in the league."""

    _attr_translation_key = "transactions"
    _attr_icon = "mdi:swap-horizontal-bold"
    _attr_event_types = sorted(set(TRANSACTION_TYPES.values()))

    def __init__(self, coordinator: EspnFantasyHockeyCoordinator) -> None:
        super().__init__(coordinator, "transactions")

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data
        for transaction in reversed(data.new_transactions):  # oldest first
            details = describe_transaction(transaction, data.league, data.player_names)
            self._trigger_event(transaction.kind, details)
        super()._handle_coordinator_update()
