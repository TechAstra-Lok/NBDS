import logging


class NotificationProvider:
    """Base interface for all notification channels."""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def send(self, donor, title, message, payload=None, request_id=None):
        """
        Send a notification to a donor.
        Returns: (bool success, str|None error_message, str|None provider_response_id)
        """
        raise NotImplementedError("Providers must implement send()")
