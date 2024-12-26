# local_research_assistant - Academic Research Assistant

A Flask app built around [Ollama](https://ollama.com) and [Semantic Scholar](https://www.semanticscholar.org) to facilitate academic research and paper summarization.

## ✨ Features

- **Natural Language Search**: Directly search for your ideas or research questions, or chat with an LLM help find better search terms
- **Paper Discovery and Ranking**: Automatically searches and ranks papers based on relevance to your research needs
- **Intelligent Summarization**: Quickly load PDFs into the conversation for AI-generated summaries of papers and their key findings
- **Research Timeline Generation**: Get a summary of how research in your field has evolved over time
- **Future Work Ideation**: Generate potential research directions and gaps in the literature
- **Export Capabilities**: Save the web page to a PDF for all of your search results, or export the chat to a PDF to save your conversation

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- Flask
- Access to a local LLM server (Ollama)

You will need Ollama downloaded and running in the background. 
Visit [https://ollama.com](https://ollama.com) to download Ollama, and follow their guide to get up and running with Llama 3.2 (the default LLM for this app).
The LLM we use is set inside of `config.py`, so you can really work with any LLM you want.

### Installation


1. Clone the repository and install the few dependencies (preferably in a virtualenv or conda env)
```bash
git clone https://github.com/andrew-silva/local_research_assistant.git
cd local_research_assistant
pip install -r requirements.txt
```
2. Start the application
```bash
python app.py
```

Visit `http://localhost:5000` in your browser to start exploring academic literature!

## 💡 Usage

1. **Search for relevant papers / Chat to refine your search**
   - Enter your research topic or question in the chat interface
   - Search immediately, or let the LLM ask a few questions to help frame the problem
   - After a few questions, the LLM will trigger the search automatically
2. **Discover Papers**
   - An LLM will rephrase the search query to find relevant papers on the [Semantic Scholar](https://www.semanticscholar.org) API
   - After finding papers, the app re-queries the API for more recommended papers
   - Once all results come in, an LLM ranks the papers for relevance to your original query
   - Summaries, citations, and links to full text are all provided for each paper
3. **Learn more about a chosen paper**
   - If full text is available, you can choose to chat with the LLM about the paper
   - To save those ideas, export the chat to a PDF when you're ready
4. **Analyze trends in the field**
   - Get AI-suggested future research directions based on the top N most relevant papers (default 10)
   - Let the LLM generate a timeline of key innovations based on the returned papers
   - Save the web-page to a PDF to save all your findings

## 🛠 Technology Stack

- **Backend**: Flask, Python
- **Frontend**: HTML, TailwindCSS, JavaScript
- **APIs/Search**: Semantic Scholar
- **AI**: Local LLM via Ollama
- **PDF Processing**: PyPDF2

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Semantic Scholar](https://www.semanticscholar.org/) for their free and very helpful API
- [Ollama](https://ollama.ai/) for local LLM capabilities
