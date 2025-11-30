"""STAC client connector for STAC API operations."""

from typing import Any

from dagster import ConfigurableResource
from pystac_client import Client

from plantation_monitoring.connectors.settings import SettingsResource


class STACResource(ConfigurableResource[Any]):
    """STAC resource for creating STAC API clients."""

    settings: SettingsResource

    def create_client(self) -> Any:
        """Create STAC client.

        :returns: Configured STAC client
        """
        return Client.open(self.settings.stac_api_url)
