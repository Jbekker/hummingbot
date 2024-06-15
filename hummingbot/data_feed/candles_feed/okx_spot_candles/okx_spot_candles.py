import logging
from typing import Optional

import numpy as np

from hummingbot.core.network_iterator import NetworkStatus
from hummingbot.data_feed.candles_feed.candles_base import CandlesBase
from hummingbot.data_feed.candles_feed.okx_spot_candles import constants as CONSTANTS
from hummingbot.logger import HummingbotLogger


class OKXSpotCandles(CandlesBase):
    _logger: Optional[HummingbotLogger] = None

    @classmethod
    def logger(cls) -> HummingbotLogger:
        if cls._logger is None:
            cls._logger = logging.getLogger(__name__)
        return cls._logger

    def __init__(self, trading_pair: str, interval: str = "1m",
                 max_records: int = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST):
        super().__init__(trading_pair, interval, max_records)

    @property
    def name(self):
        return f"okx_{self._trading_pair}"

    @property
    def rest_url(self):
        return CONSTANTS.REST_URL

    @property
    def wss_url(self):
        return CONSTANTS.WSS_URL

    @property
    def health_check_url(self):
        return self.rest_url + CONSTANTS.HEALTH_CHECK_ENDPOINT

    @property
    def candles_url(self):
        return self.rest_url + CONSTANTS.CANDLES_ENDPOINT

    @property
    def rate_limits(self):
        return CONSTANTS.RATE_LIMITS

    @property
    def intervals(self):
        return CONSTANTS.INTERVALS

    async def check_network(self) -> NetworkStatus:
        rest_assistant = await self._api_factory.get_rest_assistant()
        await rest_assistant.execute_request(url=self.health_check_url,
                                             throttler_limit_id=CONSTANTS.HEALTH_CHECK_ENDPOINT)
        return NetworkStatus.CONNECTED

    def get_exchange_trading_pair(self, trading_pair):
        return trading_pair

    async def fetch_candles(self,
                            start_time: Optional[int] = None,
                            end_time: Optional[int] = None,
                            limit: Optional[int] = CONSTANTS.MAX_RESULTS_PER_CANDLESTICK_REST_REQUEST):
        """
        Fetches candles data from the exchange.

        - Timestamp must be in seconds
        - The array must be sorted by timestamp in ascending order. Oldest first, newest last.
        - The array must be in the format: [timestamp, open, high, low, close, volume, quote_asset_volume, n_trades,
        taker_buy_base_volume, taker_buy_quote_volume]

        For API documentation, please refer to:
        https://www.okx.com/docs-v5/en/?shell#order-book-trading-market-data-get-candlesticks-history

        This endpoint allows you to return up to 3600 candles ago.

        :param start_time: the start time of the candles data to fetch
        :param end_time: the end time of the candles data to fetch
        :param limit: the maximum number of candles to fetch
        :return: the candles data
        """
        rest_assistant = await self._api_factory.get_rest_assistant()
        params = {"instId": self._ex_trading_pair, "bar": CONSTANTS.INTERVALS[self.interval]}
        if start_time:
            params["before"] = start_time * 1000
        # if end_time is None:
        #     end_time = start_time
        params["after"] = end_time * 1000
        candles = await rest_assistant.execute_request(url=self.candles_url,
                                                       throttler_limit_id=CONSTANTS.CANDLES_ENDPOINT,
                                                       params=params)
        arr = [[self.ensure_timestamp_in_seconds(row[0]), row[1], row[2], row[3], row[4], row[5], row[6], 0., 0., 0.]
               for row in candles["data"]][::-1]
        return np.array(arr).astype(float)

    def ws_subscription_payload(self):
        candle_args = [{"channel": f"candle{CONSTANTS.INTERVALS[self.interval]}", "instId": self._ex_trading_pair}]
        return {
            "op": "subscribe",
            "args": candle_args
        }

    def _parse_websocket_message(self, data: dict):
        candles_row_dict = {}
        if data is not None and "data" in data:  # data will be None when the websocket is disconnected
            candles = data["data"][0]
            candles_row_dict["timestamp"] = self.ensure_timestamp_in_seconds(candles[0])
            candles_row_dict["open"] = candles[1]
            candles_row_dict["high"] = candles[2]
            candles_row_dict["low"] = candles[3]
            candles_row_dict["close"] = candles[4]
            candles_row_dict["volume"] = candles[5]
            candles_row_dict["quote_asset_volume"] = candles[6]
            candles_row_dict["n_trades"] = 0.
            candles_row_dict["taker_buy_base_volume"] = 0.
            candles_row_dict["taker_buy_quote_volume"] = 0.
            return candles_row_dict
