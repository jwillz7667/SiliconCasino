from fastapi import HTTPException, status


class SiliconCasinoError(Exception):
    """Base exception for Silicon Casino."""

    def __init__(self, message: str, code: str | None = None):
        self.message = message
        self.code = code
        super().__init__(message)


class AuthenticationError(SiliconCasinoError):
    """Authentication failed."""

    pass


class AuthorizationError(SiliconCasinoError):
    """Authorization failed."""

    pass


class InsufficientFundsError(SiliconCasinoError):
    """Wallet has insufficient funds."""

    pass


class InvalidActionError(SiliconCasinoError):
    """Invalid game action."""

    pass


class TableFullError(SiliconCasinoError):
    """Table is full."""

    pass


class NotYourTurnError(SiliconCasinoError):
    """Not the player's turn."""

    pass


# HTTP Exceptions
def not_found(detail: str = "Resource not found") -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def bad_request(detail: str = "Bad request") -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def unauthorized(detail: str = "Unauthorized") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def forbidden(detail: str = "Forbidden") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def conflict(detail: str = "Conflict") -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
