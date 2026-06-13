class ServiceError(Exception):
    """Error de validación/regla de negocio. Los routers lo traducen a un mensaje."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
