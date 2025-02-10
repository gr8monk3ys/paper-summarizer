"""Main entry point for the Paper Summarizer application."""

from paper_summarizer.web.app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
