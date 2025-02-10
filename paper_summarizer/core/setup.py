"""Setup script for downloading required NLTK data."""

import nltk

def download_nltk_data():
    """Download required NLTK data."""
    try:
        # Download both punkt and punkt_tab data
        resources = ['punkt', 'punkt_tab', 'averaged_perceptron_tagger']
        for resource in resources:
            print(f"Downloading {resource}...")
            nltk.download(resource, quiet=True)
        print("Successfully downloaded all NLTK data.")
    except Exception as e:
        print(f"Error downloading NLTK data: {str(e)}")
        raise

if __name__ == '__main__':
    download_nltk_data()
