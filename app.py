from queue import Queue
from flask import Flask, request, render_template, jsonify, Response
import requests
import time
import logging
import json
from flask import stream_with_context
from PyPDF2 import PdfReader

from config import Config
from local_llm_helper import LocalLLM
from semantic_scholar_helper import SemanticScholarAPI


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global status queue
status_updates = Queue()


app = Flask(__name__)
semantic_scholar = SemanticScholarAPI(Config.SEMANTIC_API_KEY)
llm = LocalLLM(Config.OLLAMA_API_URL, Config.OLLAMA_MODEL)


@app.route("/", methods=["GET"])
def index():
    llm.reset()
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json()
    query = data.get("message", "").strip()
    chat_id = data.get("chat_id", None)

    if not query:
        return jsonify({"error": "Message is required"}), 400
    update_status('Thinking...')
    response = llm.chat_about_research(query, chat_id)
    if chat_id is None:
        chat_id = list(response.keys())[0]
    return jsonify({
        "chat_id": response[chat_id]["chat_id"],
        "most_recent_response": response[chat_id]["most_recent_response"],
        "ready_to_search": response[chat_id]["ready_to_search"],
        "summary": response[chat_id]["summary"]
    })


@app.route('/process-pdf', methods=['GET'])
def process_pdf():
    pdf_url = request.args.get('url')
    if not pdf_url:
        return jsonify({'error': 'PDF URL is required'}), 400

    try:
        # Download the PDF
        response = requests.get(pdf_url)
        if response.status_code != 200:
            return jsonify({'error': 'Failed to download PDF'}), 400

        # Save the PDF locally
        pdf_path = '/tmp/temp_paper.pdf'
        with open(pdf_path, 'wb') as f:
            f.write(response.content)

        # Extract text from the PDF
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text()

        if not text.strip():
            return jsonify({'error': 'No text found in the PDF'}), 400

        # Add the extracted text to the LLM context
        chat_id = str(time.time())  # Generate a new chat ID
        llm.chat_state[chat_id] = {
            "chat_id": chat_id,
            "paper_text": text,
            "full_context": "",
            "most_recent_response": "The paper's content has been loaded into the chat context.",
            "started_chat": False
        }

        return jsonify({'message': 'PDF processed successfully', 'chat_id': chat_id})

    except Exception as e:
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500


def update_status(message: str):
    status_updates.put(message)


@app.route("/status")
def status():
    def generate():
        while True:
            try:
                # Check for new status every 0.1 seconds
                message = status_updates.get(timeout=0.1)
                yield f"data: {json.dumps({'status': message})}\n\n"
            except:
                # Send heartbeat to keep connection alive
                yield f"data: {json.dumps({'heartbeat': True})}\n\n"
            time.sleep(0.1)

    return Response(generate(), mimetype='text/event-stream')


@app.route("/generate_timeline", methods=["POST"])
def generate_timeline():
    data = request.get_json()
    papers = data.get("papers", [])

    if not papers:
        return jsonify({"error": "No papers provided"}), 400

    timeline = llm.generate_timeline(papers)
    return jsonify({"timeline": timeline})


@app.route("/generate_future_work", methods=["POST"])
def generate_future_work():
    data = request.get_json()
    papers = data.get("papers", [])

    if not papers:
        return jsonify({"error": "No papers provided"}), 400

    future_work = llm.generate_future_work(papers, cutoff=Config.RELEVANT_PAPERS_FOR_FUTURE_WORK)
    return jsonify({"future_work": future_work})


@app.route("/stream_search", methods=["POST"])
def stream_search():
    # Mark us as having searched so that chats are now just chats
    llm.searched_already = True

    def generate():
        data = request.get_json()
        query = data.get("query", "").strip()
        year_filter = data.get("year_filter", Config.DEFAULT_YEAR_FILTER)

        # Step 1: Rephrase query
        update_status("Refining search query...")
        refined_query_list = llm.rephrase_query(query)
        if not refined_query_list:
            refined_query_list = [query]

        yield json.dumps({"type": "refined_query", "data": refined_query_list}) + "\n"

        # Step 2: Search papers
        update_status("Searching for relevant papers...")
        papers = []
        seen_paper_ids = set()  # Track unique papers

        for refined_query in refined_query_list:
            batch = semantic_scholar.search_papers(refined_query, year_filter)
            # Stream each batch of papers immediately
            papers_back = []
            for p in batch:
                if p.get("paperId") not in seen_paper_ids:
                    papers.append(p)
                    seen_paper_ids.add(p.get("paperId"))
                    open_pdf = p.get("openAccessPdf", None)
                    open_pdf_url = ''
                    if open_pdf is not None:
                        open_pdf_url = open_pdf.get('url')
                    papers_back.append({
                        "title": p.get("title", "Untitled"),
                        "url": p.get("url"),
                        "publication_date": p.get("publicationDate"),
                        "citation_count": p.get("citationCount", 0),
                        "authors": [a.get("name", "") for a in p.get("authors", [])],
                        "pdf_url": open_pdf_url,
                        "paper_id": p.get("paperId"),
                        "abstract": p.get("abstract", "")
                    })
            if papers_back:
                yield json.dumps({
                    "type": "papers",
                    "data": papers_back
                }) + "\n"

        # Step 3: Rank papers for relevance to the original query
        paper_relevance_scores = {}
        update_status("Rating paper relevance...")
        for paper in papers:
            paper_id = paper.get("paperId")
            try:
                relevance = llm.rate_paper_relevance(query, paper)
                paper_relevance_scores[paper_id] = relevance
                yield json.dumps({
                    "type": "relevance",
                    "data": {"paper_id": paper_id, "relevance": relevance}
                }) + "\n"
            except Exception as e:
                paper_relevance_scores[paper_id] = 0
                logger.error(f"Error rating paper {paper_id}: {e}")

        # Identify all papers that have a `tldr` `text` that is not Null,
        # and send them back immediately with the TLDR as the summary
        update_status("Summarizing the most relevant papers...")
        sorted_papers = sorted(
            papers,
            key=lambda p_id: paper_relevance_scores.get(p_id.get("paperId"), 0),
            reverse=True
        )
        papers_needing_summary = []
        for paper in sorted_papers:
            paper_id = paper.get("paperId")
            tldr = paper.get("tldr", {})
            if tldr:
                tldr = tldr.get("text")
                if tldr:
                    yield json.dumps({
                        "type": "summary",
                        "data": {
                            "paper_id": paper_id,
                            "summary": tldr
                        }
                    }) + "\n"
                elif paper.get("abstract"):
                    # Does not have a TLDR but has an abstract
                    papers_needing_summary.append(paper)
                else:
                    # Paper has no TLDR and no abstract
                    yield json.dumps({
                        "type": "summary",
                        "data": {
                            "paper_id": paper_id,
                            "summary": 'No summary available.'
                        }
                    }) + "\n"

        # Send the rest of the papers on for summarization
        for paper in papers_needing_summary:
            paper_id = paper.get("paperId")
            try:
                summary = llm.summarize_paper(query, paper)
                yield json.dumps({
                    "type": "summary",
                    "data": {"paper_id": paper_id, "summary": summary}
                }) + "\n"
            except Exception as e:
                logger.error(f"Error summarizing paper {paper_id}: {e}")

    return Response(
        stream_with_context(generate()),
        mimetype='application/x-ndjson'
    )


if __name__ == "__main__":
    app.run(debug=True)
