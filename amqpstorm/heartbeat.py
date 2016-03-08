"""AMQP-Storm Connection.Heartbeat."""
__author__ = 'eandersson'

import time
import logging
import threading

from amqpstorm.base import Stateful
from amqpstorm.exception import AMQPConnectionError

LOGGER = logging.getLogger(__name__)


class Heartbeat(Stateful):
    """Internal Heartbeat Checker."""

    def __init__(self, interval):
        super(Heartbeat, self).__init__()
        if interval < 1:
            interval = 1
        self.lock = threading.Lock()
        self._timer = None
        self._exceptions = None
        self._last_heartbeat = 0.0
        self._beats_since_check = 0
        self._interval = int(interval)
        self._threshold = self._interval * 2

    def register_beat(self):
        """Register that a frame has been received.

        :return:
        """
        self._beats_since_check += 1

    def register_heartbeat(self):
        """Register a Heartbeat.

        :return:
        """
        self._last_heartbeat = time.time()

    def start(self, exceptions):
        """Start the Heartbeat Checker.

        :param list exceptions:
        :return:
        """
        LOGGER.debug('Heartbeat Checker Started')
        with self.lock:
            self.set_state(self.OPENING)
            self._beats_since_check = 0
            self._last_heartbeat = time.time()
            self._exceptions = exceptions
            self._start_timer()
            self.set_state(self.OPEN)

    def stop(self):
        """Stop the Heartbeat Checker.

        :return:
        """
        with self.lock:
            if not self._timer:
                self.set_state(self.CLOSED)
                return
            self._timer.cancel()
            self._timer = None
            self.set_state(self.CLOSED)
        LOGGER.debug('Heartbeat Checker Stopped')

    def _check_for_life_signs(self):
        """Check if we have any sign of life.

            If we have not received a heartbeat, or any data what so ever
            we should raise an exception so that we can close the connection.

            RabbitMQ may not necessarily send heartbeats if the connection
            is busy, so we only raise if no frame has been received.

        :return:
        """
        LOGGER.debug('Checking for a heartbeat')
        current_time = time.time()
        elapsed = current_time - self._last_heartbeat
        if self._beats_since_check == 0 and elapsed > self._threshold:
            message = ('Connection dead, no heartbeat or data received in %ss'
                       % round(elapsed, 3))
            why = AMQPConnectionError(message)
            if self._exceptions is None:
                raise why
            self._exceptions.append(why)

        self._beats_since_check = 0
        if not self.is_closed:
            self._start_timer()

    def _start_timer(self):
        """Create a timer that will check for life signs on our connection.

        :return:
        """
        self._timer = threading.Timer(interval=self._interval,
                                      function=self._check_for_life_signs)
        self._timer.daemon = True
        self._timer.start()