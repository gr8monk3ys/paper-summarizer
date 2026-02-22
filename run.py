"""Main entry point for the Paper Summarizer application."""

import os

import uvicorn

if __name__ == "__main__":
    env = os.getenv("APP_ENV", "development")
    uvicorn.run(
        "paper_summarizer.web.app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        reload=env == "development",
    )
