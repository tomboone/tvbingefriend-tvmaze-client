"""TVMaze API Client with Enhanced Retry Logic and Connection Pooling."""

import logging  # Keep for default logger
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from typing import Dict, List, Any, Optional
from . import config
# Import Logger type for hinting
from logging import Logger


class TVMazeAPI:
    """Client for interacting with the TV Maze API with robust retry logic."""

    SUPPORTED_UPDATE_PERIODS = {'day', 'week', 'month'}

    # Add logger parameter with type hint
    def __init__(self, logger: Optional[Logger] = None):
        """Initializes the API client with session and enhanced retry/pool adapter."""
        from . import TVMazeReliabilityManager

        # Use provided logger or get default for this module
        # Using __name__ is standard practice for library code
        self.logger = logger or logging.getLogger(__name__)

        self.base_url: str = config.TVMAZE_API_BASE_URL.rstrip('/')

        self.reliability_manager = TVMazeReliabilityManager(logger=self.logger)

        # Use self.logger now
        self.logger.info(
            f"TVMazeAPI initialized: base_url={self.base_url}"
        )

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """Makes a GET request using the configured session with retries."""
        url = f"{self.base_url}{endpoint}"
        req_params = params or {}
        # Use self.logger
        self.logger.debug(f"Making API request: GET {url} with params {req_params}")
        
        @self.reliability_manager.reliable_api_call()
        def _request():
            response = requests.get(url, params=req_params, timeout=30)

            if response.status_code == 404:
                log_message = f"API returned 404 Not Found for {url} (Params: {req_params})."
                if endpoint == '/updates/shows' and 'since' in req_params:
                    log_message += " This might indicate no updates for the requested period."
                # Use self.logger
                self.logger.info(log_message)
                return None

            response.raise_for_status()

            try:
                return response.json()
            except requests.exceptions.JSONDecodeError as json_err:
                # Use self.logger
                self.logger.error(
                    f"Failed to decode JSON from {url}: {json_err}. Response text: {response.text[:200]}...")
                raise ValueError("Invalid JSON response from API") from json_err
        
        try:
            return _request()
        except requests.exceptions.RequestException as req_err:
            # Use self.logger
            self.logger.error(f"API request failed permanently for {url} after retries: {req_err}")
            raise

    def get_shows(self, page: int) -> Optional[List[Dict[str, Any]]]:
        """Fetches a page of shows from the TV Maze index."""
        # Use self.logger
        self.logger.info(f"Fetching shows page {page}.")
        result = self._make_request('/shows', params={'page': page})
        if result is not None and not isinstance(result, list):
            # Use self.logger
            self.logger.error(f"Unexpected non-list response for /shows page {page}: {type(result)}")
            return None
        return result

    def get_show_details(self, show_id: int, embed: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """
        Fetches full details for a specific show, optionally embedding related data.

        Args:
            show_id: The ID of the show to fetch.
            embed: A list of related data to embed, e.g., ['seasons', 'episodes'].

        Returns:
            A dictionary containing the show details, or None if not found.
        """
        self.logger.info(f"Fetching details for show ID {show_id} with embeds: {embed}.")

        params = {}
        if embed:
            params['embed[]'] = embed

        result = self._make_request(f'/shows/{show_id}', params=params)

        if result is not None and not isinstance(result, dict):
            self.logger.error(f"Unexpected non-dict response for /shows/{show_id}: {type(result)}")
            return None
        return result

    def get_seasons(self, show_id: int) -> Optional[List[Dict[str, Any]]]:
        """Fetches season data for a specific show."""
        # Use self.logger
        self.logger.info(f"Fetching seasons for show ID {show_id}.")
        result = self._make_request(f'/shows/{show_id}/seasons')
        if result is not None and not isinstance(result, list):
            # Use self.logger
            self.logger.error(f"Unexpected non-list response for /shows/{show_id}/seasons: {type(result)}")
            return None
        return result

    def get_episodes(self, show_id: int) -> Optional[List[Dict[str, Any]]]:
        """Fetches episode data for a specific show."""
        # Use self.logger
        self.logger.info(f"Fetching episodes for show ID {show_id}.")
        result = self._make_request(f'/shows/{show_id}/episodes')
        if result is not None and not isinstance(result, list):
            # Use self.logger
            self.logger.error(f"Unexpected non-list response for /shows/{show_id}/episodes: {type(result)}")
            return None
        return result

    def get_network(self, network_id: int) -> dict[str, Any] | None:
        """Fetches network details for a specific network ID."""
        # Use self.logger
        self.logger.info(f"Fetching network details for ID {network_id}.")
        result = self._make_request(f'/networks/{network_id}')
        if result is not None and not isinstance(result, dict):
            # Use self.logger
            self.logger.error(f"Unexpected non-dict response for /networks/{network_id}: {type(result)}")
            return None
        return result

    def get_webchannel(self, webchannel_id: int) -> dict[str, Any] | None:
        """Fetches webchannel details for a specific webchannel ID."""
        # Use self.logger
        self.logger.info(f"Fetching webchannel details for ID {webchannel_id}.")
        result = self._make_request(f'/webchannels/{webchannel_id}')
        if result is not None and not isinstance(result, dict):
            # Use self.logger
            self.logger.error(f"Unexpected non-dict response for /webchannels/{webchannel_id}: {type(result)}")
            return None
        return result

    def get_show_updates(self, period: str = 'day') -> Optional[Dict[str, int]]:
        """Fetches recently updated show IDs using the API's 'since' parameter."""
        if period not in self.SUPPORTED_UPDATE_PERIODS:
            # Use self.logger
            self.logger.error(f"Unsupported update period '{period}'. Use one of {self.SUPPORTED_UPDATE_PERIODS}.")
            return None

        # Use self.logger
        self.logger.info(f"Fetching show updates since last {period} using API 'since' parameter.")
        api_params = {'since': period}
        updates = self._make_request('/updates/shows', params=api_params)

        if updates is None:
            # Use self.logger
            self.logger.info(
                f"API returned 404 or request failed for /updates/shows?since={period}. Assuming no updates.")
            return {}

        if not isinstance(updates, dict):
            # Use self.logger
            self.logger.error(f"Unexpected response format from /updates/shows?since={period}: {type(updates)}")
            return None

        valid_updates = {show_id: ts for show_id, ts in updates.items() if isinstance(ts, int)}
        if len(valid_updates) != len(updates):
            # Use self.logger
            self.logger.warning(
                f"Some updates received from /updates/shows?since={period} had non-integer timestamps and were "
                f"ignored."
            )
        # Use self.logger
        self.logger.info(f"Obtained {len(valid_updates)} show updates since last {period} directly from API.")

        return valid_updates
