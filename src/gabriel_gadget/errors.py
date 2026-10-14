class GadgetError(Exception):
    """An error safe to report to a gadget (without provider payloads or secrets)."""

    def __init__(self, code, message, status=400):
        super().__init__(message)
        self.code = code
        self.status = status


class BackendError(GadgetError):
    pass
