import nltk
import requests
from bs4 import BeautifulSoup
from sumy.parsers.plaintext import PlaintextParser
from sumy.nlp.tokenizers import Tokenizer
from flask import Flask, render_template, request
from sumy.summarizers.lsa import LsaSummarizer  # import LsaSummarizer
import gensim  # import gensim
from src import summarizer

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['DEBUG'] = True

@app.route('/',  methods=['GET', 'POST'])
def index():
  if request.method == 'POST':
    # Get the values of the input fields
    url = request.form['url']
    num_sentences = int(request.form['num_sentences'])

    # Set the values to the desired variables
    summary = summarizer.summarize(url, num_sentences)

    # Output the results
    return render_template('index.html', summary=summary)
  return render_template('index.html')

@app.route('/summary', methods=['GET', 'POST'])
def summary():
  if request.method == 'POST':
    # Get the values of the input fields
    url = request.form['url']
    num_sentences = int(request.form['num_sentences'])

    # Set the values to the desired variables
    summary = summarizer.summarize(url, num_sentences)

    # Output the results
    # return f'Input 1: {var1}<br>Input 2: {var2}'
    return render_template('index.html', summary=summary)
  else:
    return '''
      <form method="POST">
        <input name="input1" type="text">
        <input name="input2" type="text">
        <input type="submit">
      </form>
    '''    

if __name__ == '__main__':
  app.run()
