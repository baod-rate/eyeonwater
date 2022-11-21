"""Config flow for Eye On Water integration."""
import asyncio
import logging
from typing import Any, Dict

from aiohttp import ClientError
from .eow import Account, Client, EyeOnWaterAPIError, EyeOnWaterAuthError

import voluptuous as vol

from homeassistant import config_entries, core, exceptions
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_DOMAIN
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_DOMAIN, default="com"): str, vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)

def create_account_from_config(data: Dict[str, Any]) -> Account:
    try:
        domain = data[CONF_DOMAIN]
    except KeyError:
        domain = "com"

    if domain == "com":
        eow_hostname = "eyeonwater.com"
        metric_measurement_system = False
    elif domain == "ca":
        eow_hostname = "eyeonwater.ca"
        metric_measurement_system = True
    else:
        raise WrongDomain(f"Unsupported domain {domain}. Only 'com' and 'ca' are supported")

    account = Account(eow_hostname=eow_hostname, username=data[CONF_USERNAME], password=data[CONF_PASSWORD], metric_measurement_system=metric_measurement_system)
    return account

async def validate_input(hass: core.HomeAssistant, data):
    """Validate the user input allows us to connect.

    Data has the keys from DATA_SCHEMA with values provided by the user.
    """
    client_session = aiohttp_client.async_get_clientsession(hass)
    account = create_account_from_config(data=data)
    client = Client(client_session, account)

    try:
        await client.authenticate()
    except (asyncio.TimeoutError, ClientError, EyeOnWaterAPIError) as error:
        raise CannotConnect from error
    except EyeOnWaterAuthError as error:
        raise InvalidAuth(error) from error

    # Return info that you want to store in the config entry.
    return {"title": account.username}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Eye On Water."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""

        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if not errors:
                    # Ensure the same account cannot be setup more than once.
                    await self.async_set_unique_id(user_input[CONF_USERNAME])
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

class WrongDomain(exceptions.HomeAssistantError):
    """Error to indicate wrong EOW domain."""


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(exceptions.HomeAssistantError):
    """Error to indicate there is invalid auth."""
