import nltk
import requests
from bs4 import BeautifulSoup
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from sumy.summarizers.lsa import LsaSummarizer  # import LsaSummarizer
import gensim  # import gensim

def summarize(url, num_sentences):
    # Send a GET request to the URL and retrieve the response
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    # Extract the text of the research paper
    research_paper = soup.get_text()

    parser = PlaintextParser.from_string(research_paper, Tokenizer("english"))
    summarizer = LsaSummarizer()
    summary = summarizer(parser.document, num_sentences)  
    # Concatenate the summary sentences into a single string
    summary_text = " ".join([str(sentence) for sentence in summary])
    return summary_text

if __name__ == '__main__':
    summary_text = summarize(url)
    print(summary_text)
