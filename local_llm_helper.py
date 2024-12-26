import re
import requests
import logging
from typing import List, Dict, Any
import time

from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_bracket_content(input_string, angle: bool = False):
    """
    Extracts all content between [ and ] in the given string.

    Args:
        input_string (str): The string to parse.
        angle (bool): Should we use angle brackets? Defaults ot False (so we use square brackets)
    Returns:
        list: A list of all content found between [ and ].
    """
    pattern = r"\[(.*?)\]"
    if angle:
        pattern = r'<<(.*?)>>'
    matches = re.findall(pattern, input_string)
    return matches


def add_citations(sorted_papers: list = None, citations: Dict = None, ref_text: str = ''):
    # Add bibliography
    bibliography = ''
    for paper in sorted_papers:
        citation = citations.get(paper['paper_id'])
        if citation and citation in ref_text:
            author_list = paper.get('authors', [])
            if len(author_list) > 5:
                author_list = ', '.join(author_list[:5]) + ' et al.'
            else:
                author_list = ', '.join(author_list)
            if not bibliography:
                bibliography = "\n\n## References\n\n"
            bibliography += f"{citation} {paper['title']} - {author_list} \n \n"
    return bibliography


class LocalLLM:
    def __init__(self, api_url: str, model: str):
        self.api_url = api_url
        self.model = model
        self.session = requests.Session()
        self.chat_state = {}
        self.original_search_query = ''
        self.searched_already = False

    def reset(self):
        self.session = requests.Session()
        self.chat_state = {}
        self.original_search_query = ''
        self.searched_already = False

    def generate(self, prompt: str, max_retries: int = Config.MAX_RETRIES, stops=None) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "temperature": 0.8,
            "num_ctx": 32000,
        }
        if stops is not None:
            payload['stop'] = stops

        for attempt in range(max_retries):
            try:
                response = self.session.post(
                    self.api_url,
                    json=payload,
                    timeout=Config.TIMEOUT
                )
                response.raise_for_status()
                return response.json().get('response', '')
            except requests.exceptions.RequestException as e:
                logger.error(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt == max_retries - 1:
                    return ""
        return ""

    def chat_to_search(self, query: str, chat_id: str = None) -> Dict[str, Any]:
        if not chat_id:
            chat_id = str(time.time())
            self.chat_state[chat_id] = {
                "chat_id": chat_id,
                "original_query": query,
                "summary": "",
                "full_context": "",
                "ready_to_search": False,
                "most_recent_response": ""
            }
            prompt = f"You are an academic research assistant AI that helps researchers compose search queries" \
                     f" to find all of the most important related work in their field. The researcher will" \
                     f" give you an initial query, and you should ask questions to get a better sense for the" \
                     f" research questions and keywords to find the best related works." \
                     f"\n\n" \
                     f"After each researcher query, first decide if you have enough information to search." \
                     f" If you are ready, provide a detailed summary of the ideas," \
                     f" which will be sent to an LLM to rephrase into search queries. " \
                     f"Put ONLY the summary in [brackets], do not include dialogue or chit chat inside [brackets]." \
                     f" If you don't have enough information, ask one question at a time to the researcher to help " \
                     f"get a better idea of what to search for." \
                     f"\n\n" \
                     f"Researcher: {query}\n\nAI Assistant: "
        else:
            prompt = f"{self.chat_state[chat_id]['full_context']}\n\nResearcher: {query}\n\nAI Assistant: "

        response = self.generate(prompt, stops=['Researcher:', '\nResearcher:', 'Researcher: ',
                                                '\nResearcher: ', '\nAI Assistant:', '\nAI Assistant: '])
        response = re.sub(r'\n', '<br />', response)
        full_context = f"{prompt}{response}"
        self.chat_state[chat_id]["full_context"] = full_context
        response = re.sub(r'\[brackets]|\[]', '', response)  # Remove [brackets] or []
        response = re.sub(r'\n', '<br />', response)
        summary = extract_bracket_content(response)
        # Can't believe I have to guard against this...
        if summary and len(summary[0]) > 0:
            self.chat_state[chat_id]["ready_to_search"] = True
            self.chat_state[chat_id]["summary"] = summary
        self.chat_state[chat_id]["most_recent_response"] = response
        return self.chat_state

    def chat_about_research(self, query: str, chat_id: str = None) -> Dict[str, Any]:
        if self.searched_already:
            if not chat_id:
                chat_id = str(time.time())
            if self.chat_state[chat_id]["started_chat"]:
                scratch_pad = ''
                if self.chat_state[chat_id]["summary"]:
                    scratch_pad = f"Notes to self: {self.chat_state[chat_id]['summary']}\n\n"
                prompt = f"{self.chat_state[chat_id]['full_context']}\n\nResearcher: {query}" \
                         f"\n\n{scratch_pad}Expert Assistant: "
            else:
                paper_text = self.chat_state[chat_id]["paper_text"]
                prompt = f"You are an expert helping a researcher to read a paper." \
                         f" The researcher is interested in preparing for a project" \
                         f" about \"{self.original_search_query}\"." \
                         f"\nYou will help them work through ideas for this," \
                         f" bolstered by the recent paper you just read:\n{paper_text}\n\n" \
                         f"If you want to do any reasoning or make notes that don't go to the researcher," \
                         f" put such notes in <<double angle brackets>>. The researcher WILL NOT see text in" \
                         f" <angle brackets>.\nFinally, keep it concise and informative." \
                         f"\nResearcher: {query}\n\nExpert Assistant: "
                self.chat_state[chat_id]["full_context"] = prompt
                self.chat_state[chat_id]["most_recent_response"] = ""
                self.chat_state[chat_id]["summary"] = ""
                self.chat_state[chat_id]["ready_to_search"] = False
                self.chat_state[chat_id]["started_chat"] = True

            response = self.generate(prompt, stops=['Researcher:', '\nResearcher:', 'Researcher: ',
                                                    '\nResearcher: ', '\nExpert Assistant:', '\nExpert Assistant: '])
            scratch_pad = extract_bracket_content(response, angle=True)
            response = re.sub(r'\n', '<br />', response)
            if scratch_pad:
                self.chat_state[chat_id]["summary"] += f"{scratch_pad}\n"
                response = re.sub(r'<<.*?>>', '', response)  # Remove scratch pad for the response
            self.chat_state[chat_id]["full_context"] += f"\n\nResearcher: {query}\n\nExpert Assistant: {response}"
            self.chat_state[chat_id]["most_recent_response"] = response

            return self.chat_state
        else:
            return self.chat_to_search(query, chat_id)

    def rephrase_query(self, query: str) -> list:
        self.original_search_query = query
        prompt = f"""Task: Rephrase the following query to optimize it for academic paper search.
Guidelines:
- Add relevant academic keywords and phrases
- Focus on technical/scientific terminology
- Keep it concise and specific
- Put the rephrased queries inside square brackets

For example:

Query: Preference learning for autonomous driving style

Reasoning: The researcher is interested in finding related work about driving styles, probably from implicit or
 explicit feedback from a driver. This could encompass fields like personalization, imitation learning,
  style transfer, or even classical controls. 
  I will create a short list of search queries to find the best papers from this list.

Rephrased query: [Preference learning AND (Driving style OR autonomous driving style)] 
[(Autonomous vehicles OR Self-driving cars) AND (Personalization) OR (Style)] 
[(Style transfer OR Personalization OR preferences) AND (Imitation learning OR Reinforcement learning OR control)]

Your query is:

Query: "{query}"

Reasoning:"""
        response = self.generate(prompt).strip()

        return extract_bracket_content(response)

    def rate_paper_relevance(self, query: str, paper: Dict[str, Any]) -> float:
        abstract = paper.get('abstract', '')
        if abstract is None or len(abstract) < 1:
            # If we don't have an abstract, get a TLDR
            tldr = paper.get("tldr", {})
            if tldr:
                tldr = tldr.get("text")
                abstract = tldr
        # If we still don't have anything, give up.
        if abstract is None or len(abstract) < 1:
            return 0.0
        prompt = f"""Rate the relevance of this paper to the query on a scale of 0-100:

Query: {query}
Title: {paper.get('title', 'N/A')}
Abstract: {abstract}

Consider:
- Direct relevance to query topic
- Methodology alignment
- Potential usefulness
- Research focus match

Return only the numerical score (0-100):"""

        try:
            response = self.generate(prompt).strip()
            return float(response)
        except:
            return 0.0

    def summarize_paper(self, original_query, paper: Dict[str, Any]) -> str:
        prompt = f"""Summarize the following academic paper in 3-4 informative sentences, 
        focusing on how it relates to the original query:

Original query: {original_query}
Title: {paper.get('title', 'N/A')}
Authors: {', '.join(author.get('name', '') for author in paper.get('authors', []))}
Abstract: {paper.get('abstract', 'N/A')}

Focus on:
- Main research contribution
- Key findings or methodology
- Practical implications

Remember to avoid extraneous language or colloquial commentary, only return the paper summary.

Summary:"""
        paper_summary = self.generate(prompt).strip()
        return paper_summary

    def generate_timeline(self, papers: List[Dict[str, Any]], with_citations: bool = True) -> str:
        if not papers:
            return "No papers available to generate timeline."

        # Sort papers by date
        sorted_papers = sorted(
            [p for p in papers if p.get('publication_date')],
            key=lambda x: x.get('publication_date', ''),
            reverse=True
        )
        citations = {}
        if with_citations:
            for i, paper in enumerate(sorted_papers, 1):
                citations[paper['paper_id']] = f"[{i}]"
                paper['citation_number'] = i

        papers_text = "\n".join([
            f"- {paper.get('publication_date', 'N/A')}: {paper.get('title', 'N/A')} "
            f"{citations.get(paper['paper_id'], '')}: {paper.get('summary', 'No summary available')}"
            for paper in sorted_papers
        ])

        prompt = f"""Create a research timeline for the following papers. Do not add new papers, use ONLY this list:

{papers_text}

Guidelines:
- Focus on evolution of ideas and methodologies
- Highlight key breakthroughs and innovations
- Use bullet points with years
- Reference specific papers with citation numbers in square brackets
- Do not include a list of references, I will add that
- Keep it concise but informative
- Format for display in HTML

Timeline:"""
        timeline = self.generate(prompt,
                                 stops=["References:", "\nReferences:", "Bibliography:", "\nBibliography:"]).strip()
        if with_citations:
            # Add bibliography
            bibliography = add_citations(sorted_papers=sorted_papers, citations=citations, ref_text=timeline)
            timeline += bibliography

        return timeline

    def generate_future_work(self, papers: List[Dict[str, Any]], with_citations: bool = True, cutoff: int = 10) -> str:
        if not papers:
            return "No papers available to generate future work ideas."
        papers = sorted(
            papers,
            key=lambda p_id: p_id.get('relevance', 0),
            reverse=True
        )
        papers = papers[:cutoff]
        citations = {}
        if with_citations:
            for i, paper in enumerate(papers, 1):
                citations[paper['paper_id']] = f"[{i}]"

        papers_text = "\n".join([
            f"- {paper.get('title', 'N/A')} {citations.get(paper['paper_id'], '')}:"
            f"\n{paper.get('summary', 'No summary available')}"
            for paper in papers
        ])

        prompt = f"""Identify fruitful paths or ideas for future work based on this body of recent work:

{papers_text}

Guidelines:
- Think about the evolution of ideas and methodologies while looking for key breakthroughs and innovations
- Reference specific papers using citation numbers
- Keep it _CONCISE_ but informative, do not add pleasantries or commentary
- Do not include a list of references, I will add that
- Format for display in HTML

Future work ideas:"""

        future_work = self.generate(prompt).strip()

        if with_citations:
            bibliography = add_citations(sorted_papers=papers, citations=citations, ref_text=future_work)
            future_work += bibliography

        return future_work
