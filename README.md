# Paper Summarizer

![Dashboard](public/images/dashboard.png)

A modern web application that helps researchers and students quickly summarize academic papers using advanced language models. Built with Flask and Together AI, it provides an intuitive interface for summarizing papers from text, URLs, or file uploads.

## Features

- **Multiple Input Methods**: 
  - Direct text input
  - URL scraping
  - File upload (supports .txt, .md, .rst)
  - Batch processing for multiple files

- **Advanced Summarization**:
  - Choice of language models (T5-Small, DeepSeek-R1)
  - Local or Together AI processing
  - Configurable summary length
  - Optional citation handling

- **Modern Interface**:
  - Clean, responsive design with Tailwind CSS
  - Real-time processing feedback
  - Error handling and validation
  - Mobile-friendly layout

## Installation

1. Clone the repository:
```bash
git clone https://github.com/gr8monk3ys/paper-summarizer.git
cd paper-summarizer
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up environment variables:
```bash
# Create a .env file with:
TOGETHER_API_KEY=your_api_key_here
FLASK_APP=paper_summarizer.web.app
FLASK_ENV=development
```

## Usage

1. Start the Flask server:
```bash
flask run
```

2. Open your browser and navigate to `http://localhost:5000`

3. Choose your preferred input method:
   - Paste paper text directly
   - Enter a paper URL
   - Upload a paper file
   - Batch process multiple files

4. Configure summarization options:
   - Select model type (T5-Small or DeepSeek-R1)
   - Choose provider (Local or Together AI)
   - Set number of sentences
   - Toggle citation handling

5. Click "Generate Summary" and view the results

## Development

- **Testing**: Run the test suite with:
```bash
python -m pytest tests/
```

- **Code Style**: Follow PEP 8 guidelines
- **Documentation**: Add docstrings for new functions
- **Error Handling**: Include appropriate error messages

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Together AI for providing the API
- Flask team for the excellent web framework
- Tailwind CSS for the styling framework
