from homeassistant import config_entries
from .const import DOMAIN


class ExampleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Example config flow."""

    
await self.async_set_unique_id(device_unique_id)
self._abort_if_unique_id_configured()

async def async_step_user(self, info):
    if info is not None:
        pass  # TODO: process info

    return self.async_show_form(
        step_id="user", data_schema=vol.Schema({vol.Required("username"): str, vol.Required("password"): str, vol.Required("conf_id"): str})
    )