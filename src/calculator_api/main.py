"""Entry point for the Calculator API server."""

import uvicorn

from calculator_api.app import create_app
from calculator_api.config import Settings


def main() -> None:
    """Load settings, create the application, and start the server."""
    settings = Settings()
    app = create_app(settings.database_url)
    uvicorn.run(app, host="0.0.0.0", port=settings.port)


if __name__ == "__main__":
    main()
