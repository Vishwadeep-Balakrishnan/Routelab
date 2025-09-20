class RouteLabError(Exception):
    """Base exception for routelab."""


class SimulatedDropError(RouteLabError):
    """Raised when a simulated network drop occurs."""


class SimulatedTimeoutError(RouteLabError):
    """Raised when a simulated timeout occurs."""


class ReplayMissError(RouteLabError):
    """Raised when replay mode is active but no recorded interaction matches."""
