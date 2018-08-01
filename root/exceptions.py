class CustomException(Exception):
    """
    Baee throwable class to distinguish expected with non-expected error. Expected error are shown to the user,
    Unexpected errors are shown and reported to sentry as well
    """
    pass


class CustomAssertionError(CustomException):
    """
    To throw when an expected error occurs because of user's fault.
    """

    pass
