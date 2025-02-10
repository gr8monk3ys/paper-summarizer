"""Web routes for the Paper Summarizer application."""

import os
from pathlib import Path
from flask import (
    Blueprint, render_template, request, jsonify, 
    current_app, send_from_directory, abort
)
from werkzeug.utils import secure_filename
from paper_summarizer.core.summarizer import PaperSummarizer, ModelType, ModelProvider

bp = Blueprint('main', __name__)

def allowed_file(filename):
    """Check if a file has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

@bp.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')

@bp.route('/library')
def library():
    """Render the library page."""
    return render_template('library.html')

@bp.route('/batch')
def batch():
    """Render the batch processing page."""
    return render_template('batch.html')

@bp.route('/analytics')
def analytics():
    """Render the analytics page."""
    return render_template('analytics.html')

@bp.route('/settings')
def settings():
    """Render the settings page."""
    return render_template('settings.html')

@bp.route('/models')
def get_models():
    """Get available models."""
    summarizer = PaperSummarizer()
    return jsonify(summarizer.get_available_models())

@bp.route('/summarize', methods=['POST'])
def summarize():
    """Handle summarization requests."""
    try:
        source_type = request.form.get('source_type', 'url')
        num_sentences = int(request.form.get('num_sentences', current_app.config['DEFAULT_NUM_SENTENCES']))
        model_type = request.form.get('model_type', current_app.config['DEFAULT_MODEL'])
        provider = request.form.get('provider', current_app.config['DEFAULT_PROVIDER'])
        keep_citations = request.form.get('keep_citations', 'false').lower() == 'true'
        
        # Validate number of sentences
        if num_sentences < current_app.config['MIN_SENTENCES'] or num_sentences > current_app.config['MAX_SENTENCES']:
            return jsonify({
                'error': f'Number of sentences must be between {current_app.config["MIN_SENTENCES"]} and {current_app.config["MAX_SENTENCES"]}'
            }), 400
        
        try:
            # Initialize summarizer with model type
            summarizer = PaperSummarizer(
                model_type=ModelType(model_type),
                provider=ModelProvider(provider)
            )
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        
        # Handle different source types
        if source_type == 'url':
            url = request.form.get('url')
            if not url:
                return jsonify({'error': 'URL is required'}), 400
            summary = summarizer.summarize_from_url(url, num_sentences)
            
        elif source_type == 'text':
            text = request.form.get('text')
            if not text:
                return jsonify({'error': 'Text is required'}), 400
            summary = summarizer.summarize(text, num_sentences)
            
        elif source_type == 'file':
            if 'file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400
                
            file = request.files['file']
            if file.filename == '':
                return jsonify({'error': 'No file selected'}), 400
                
            if not allowed_file(file.filename):
                return jsonify({'error': 'File type not allowed'}), 400
                
            filename = secure_filename(file.filename)
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                summary = summarizer.summarize_from_file(filepath, num_sentences)
            finally:
                # Clean up the uploaded file
                os.unlink(filepath)
                
        else:
            return jsonify({'error': 'Invalid source type'}), 400
        
        if summary is None:
            return jsonify({'error': 'Failed to generate summary'}), 500
            
        return jsonify({
            'summary': summary,
            'model_info': {
                'type': model_type,
                'provider': provider
            }
        })
        
    except Exception as e:
        current_app.logger.error(f'Error during summarization: {str(e)}')
        return jsonify({'error': str(e)}), 500

@bp.route('/batch', methods=['POST'])
def process_batch():
    """Handle batch processing requests."""
    try:
        # Check if files were provided
        if 'files[]' not in request.files:
            return jsonify({'error': 'No files provided'}), 400
            
        files = request.files.getlist('files[]')
        if not files:
            return jsonify({'error': 'No files selected'}), 400
            
        num_sentences = int(request.form.get('num_sentences', current_app.config['DEFAULT_NUM_SENTENCES']))
        model_type = request.form.get('model_type', current_app.config['DEFAULT_MODEL'])
        provider = request.form.get('provider', current_app.config['DEFAULT_PROVIDER'])
        keep_citations = request.form.get('keep_citations', 'false').lower() == 'true'
        
        try:
            # Initialize summarizer
            summarizer = PaperSummarizer(
                model_type=ModelType(model_type),
                provider=ModelProvider(provider)
            )
        except ValueError as e:
            return jsonify({'error': str(e)}), 400
        
        summaries = []
        for file in files:
            if file.filename == '' or not allowed_file(file.filename):
                continue
                
            filename = secure_filename(file.filename)
            filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            
            # Ensure upload directory exists
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            file.save(filepath)
            
            try:
                summary = summarizer.summarize_from_file(filepath, num_sentences, keep_citations)
                if summary:
                    summaries.append({
                        'filename': filename,
                        'summary': summary
                    })
            finally:
                # Clean up the uploaded file
                if os.path.exists(filepath):
                    os.unlink(filepath)
        
        if not summaries:
            return jsonify({'error': 'No valid files processed'}), 400
            
        return jsonify({
            'summaries': summaries,
            'model_info': {
                'type': model_type,
                'provider': provider
            }
        })
        
    except Exception as e:
        current_app.logger.error(f'Error during batch processing: {str(e)}')
        return jsonify({'error': str(e)}), 500

@bp.route('/api/settings', methods=['GET'])
def get_settings():
    """Get user settings."""
    settings = {
        'defaultModel': current_app.config['DEFAULT_MODEL'],
        'summaryLength': current_app.config['DEFAULT_NUM_SENTENCES'],
        'citationHandling': 'remove',
        'autoSave': True
    }
    return jsonify(settings)

@bp.route('/api/settings', methods=['POST'])
def save_settings():
    """Save user settings."""
    try:
        data = request.get_json()
        # Here you would typically save these settings to a database
        # For now, we'll just return success
        return jsonify({'status': 'success'})
    except Exception as e:
        current_app.logger.error(f'Error saving settings: {str(e)}')
        return jsonify({'error': str(e)}), 500

@bp.route('/api/analytics')
def get_analytics():
    """Get analytics data."""
    # Here you would typically fetch this data from a database
    # For now, we'll return mock data
    analytics = {
        'totalSummaries': 100,
        'modelUsage': {
            't5-small': 60,
            'deepseek-r1': 40
        },
        'averageLength': 5.5,
        'uniqueModels': 2
    }
    return jsonify(analytics)
