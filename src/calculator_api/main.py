"""Entry point for the Calculator API server."""

import uvicorn

from calculator_api.app import create_app
from calculator_api.config import Settings


def main() -> None:
    """Load settings, create the application, and start the server.

    Instantiates :class:`~calculator_api.config.Settings`, builds a FastAPI
    application via :func:`~calculator_api.app.create_app`, and hands it to
    ``uvicorn.run`` bound to the configured port.
    """
    settings = Settings()
    app = create_app(settings)
    uvicorn.run(app, host="0.0.0.0", port=settings.port)


if __name__ == "__main__":
    main()
