#!/usr/bin/env python3
"""Run the STAC API server."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "plantation_monitoring.api.stac_api:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )

