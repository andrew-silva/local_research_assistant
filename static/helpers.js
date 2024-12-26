let currentResults = [];
let sortAscending = false;
let paperData = new Map();
let chatHistory = [];
let activeChatId = null;

async function exportToPDF() {
    try {
        const chatMessages = Array.from(document.querySelectorAll('.chat-message')).map(msg => ({
            text: msg.innerHTML.replace(/<br\s*\/?>/g, '\n'), // Replace <br /> or <br> with \n
            isUser: msg.classList.contains('user-message')
        }));

        const { jsPDF } = window.jspdf;
        const doc = new jsPDF({
            orientation: 'portrait',
            unit: 'mm',
            format: 'a4'
        });

        const margin = 10;
        const pageWidth = doc.internal.pageSize.getWidth() - 2 * margin;
        const pageHeight = doc.internal.pageSize.getHeight() - 2 * margin;
        let cursorY = margin;

        doc.setFont('Arial');
        doc.setFontSize(12);

        chatMessages.forEach(msg => {
            const text = `${msg.isUser ? 'You:' : 'AI Assistant:'}\n${msg.text.replace(/<br \/>/g, '\n')}`;
            const lines = doc.splitTextToSize(text, pageWidth);

            if (cursorY + lines.length * 7 > pageHeight) {
                doc.addPage();
                cursorY = margin;
            }

            // Different styling for user and assistant messages
            doc.setFillColor(msg.isUser ? 235 : 247, msg.isUser ? 248 : 250, 255);
            doc.rect(margin, cursorY - 3, pageWidth, lines.length * 7 + 6, 'F');

            doc.setTextColor(msg.isUser ? 30 : 60);
            doc.text(lines, margin + 5, cursorY);
            cursorY += lines.length * 7 + 10;
        });

        doc.save('chat_history.pdf');
    } catch (error) {
        console.error('Error generating PDF:', error);
        alert('An error occurred while generating the PDF. Please try again.');
    }
}

document.getElementById('exportToPDF').addEventListener('click', exportToPDF);

// Utility functions
function showError(message) {
    const errorAlert = document.getElementById('errorAlert');
    const errorMessage = document.getElementById('errorMessage');
    errorMessage.textContent = message;
    errorAlert.classList.remove('hidden');
}

function updatePaperData(paper) {
    const existing = paperData.get(paper.paper_id) || {};
    paperData.set(paper.paper_id, { ...existing, ...paper });
}

function updatePaperCard(paperId, summary) {
    const card = document.querySelector(`[data-paper-id="${paperId}"]`);
    if (card) {
        const summaryElement = card.querySelector('.summary-placeholder');
        if (summaryElement) {
            summaryElement.textContent = summary;
            summaryElement.classList.remove('animate-pulse', 'bg-gray-100');
        }
    }
}
document.getElementById('query').addEventListener('input', function () {
    this.style.height = 'auto'; // Reset height to measure full scroll height
    this.style.height = `${this.scrollHeight}px`; // Set height based on scroll height
});
function hideError() {
    document.getElementById('errorAlert').classList.add('hidden');
}
function updateLoadingStatus(message) {
    document.getElementById('loadingStatus').textContent = message;
}
function formatDate(dateString) {
    if (!dateString) return 'Date unknown';
    try {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short' });
    } catch (e) {
        return dateString;
    }
}
function initializeStatusUpdates() {
    const evtSource = new EventSource("/status");
    evtSource.onmessage = function(event) {
        const data = JSON.parse(event.data);
        if (data.status) {
            updateLoadingStatus(data.status);
        }
    };
    return evtSource;
}

async function handleChat() {
    const query = document.getElementById('query').value.trim();
    if (!query) return;

    addChatMessage(query, true); // Add user message
    document.getElementById('query').value = '';
    const loading = document.getElementById('loading');
    loading.classList.remove('hidden');

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: query,
                chat_id: activeChatId
            })
        });

        const data = await response.json();

        if (data.error) {
            showError(data.error);
            return;
        }

        if (data.chat_id) {
            activeChatId = data.chat_id;
        }
        if (data.ready_to_search) {
            addChatMessage("Got it! I am putting a search query into the box below, and will begin looking now.")
            const query = document.getElementById('query');
            query.value = data.summary;
            query.style.height = 'auto';
            query.style.height = `${query.scrollHeight}px`;
            document.getElementById('searchButton').click();
            query.value = ''
            addChatMessage(`Searched for: "${data.summary}"`, false)
        } else if (data.most_recent_response) {
            addChatMessage(data.most_recent_response, false); // Add AI message
            loading.classList.add('hidden');
        }

    } catch (error) {
        showError('Error in chat: ' + error.message);
    }
}

function addChatMessage(text, isUser) {
    const chatContainer = document.getElementById('chatContainer');
    const messageDiv = document.createElement('div');

    messageDiv.className = `chat-message ${isUser ? 'user-message' : 'assistant-message'} p-3 rounded-lg mb-2 ${
        isUser ? 'bg-blue-100 text-blue-900' : 'bg-gray-100 text-gray-900'
    }`;

    // Replace newlines with <br> for proper rendering
    messageDiv.innerHTML = text.replace(/\n/g, '<br />');

    chatContainer.appendChild(messageDiv);

    // Auto-scroll to the bottom
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

function toggleSection(section) {
  const content = document.getElementById(`${section}Output`);
  const icon = document.getElementById(`${section}Icon`);
  const isHidden = content.classList.contains('hidden');

  content.classList.toggle('hidden');
  icon.style.transform = isHidden ? 'rotate(180deg)' : '';
}

async function generateTimeline() {
    const papers = Array.from(paperData.values());
    if (papers.length === 0) {
        showError('No papers available to generate timeline');
        return;
    }

    try {
        // Show loading state
        const loading = document.getElementById('loading');
        const loadingStatus = document.getElementById('loadingStatus');
        loading.classList.remove('hidden');
        loadingStatus.textContent = 'Generating research timeline...';

        const response = await fetch('/generate_timeline', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ papers })
        });

        const data = await response.json();
        if (data.timeline) {
            const timelineSection = document.getElementById('timelineSection');
            const timelineOutput = document.getElementById('timelineOutput');
            timelineSection.classList.remove('hidden');
            timelineOutput.innerHTML = marked.parse(data.timeline);
            timelineOutput.classList.remove('hidden');
            document.getElementById('timelineIcon').style.transform = 'rotate(180deg)';
        }
    } catch (error) {
        showError('Error generating timeline: ' + error.message);
    } finally {
        loading.classList.add('hidden');
    }
}

async function generateFutureWork() {
    const papers = Array.from(paperData.values());
    if (papers.length === 0) {
        showError('No papers available to generate future work ideas');
        return;
    }

    try {
        // Show loading state
        const loading = document.getElementById('loading');
        const loadingStatus = document.getElementById('loadingStatus');
        loading.classList.remove('hidden');
        loadingStatus.textContent = 'Generating future work ideas...';

        const response = await fetch('/generate_future_work', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ papers })
        });

        const data = await response.json();
        if (data.future_work) {
            const futureWorkSection = document.getElementById('futureWorkSection');
            const futureWorkOutput = document.getElementById('futureWorkOutput');
            futureWorkSection.classList.remove('hidden');
            futureWorkOutput.innerHTML = marked.parse(data.future_work);
            futureWorkOutput.classList.remove('hidden');
            document.getElementById('futureWorkIcon').style.transform = 'rotate(180deg)';
          }
    } catch (error) {
        showError('Error generating future work ideas: ' + error.message);
    } finally {
        loading.classList.add('hidden');
    }
}

function createPaperCard(paper) {
    const card = document.createElement('div');
    card.className = 'paper-card border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow';
    card.setAttribute('data-paper-id', paper.paper_id);

    const titleLink = document.createElement('a');
    titleLink.href = paper.url || '#';
    titleLink.target = '_blank';
    titleLink.rel = 'noopener noreferrer';
    titleLink.className = 'text-lg font-semibold text-blue-600 hover:text-blue-800 block mb-2';
    titleLink.textContent = paper.title;

    const metadata = document.createElement('p');
    metadata.className = 'text-sm text-gray-600 mb-3';
    const relevanceText = paper.relevance ? `Relevance: ${Math.round(paper.relevance)}% • ` : '';
    metadata.innerHTML = `
        ${relevanceText}
        ${paper.authors.join(', ')} •
        ${formatDate(paper.publication_date)} •
        ${paper.citation_count} citations
    `;

    const summary = document.createElement('p');
    summary.className = 'summary-placeholder text-gray-700 mb-3 animate-pulse bg-gray-100 p-2 rounded';
    summary.textContent = 'Generating summary...';

        const links = document.createElement('div');
    links.className = 'flex gap-4';

    if (paper.url) {
        const paperLink = document.createElement('a');
        paperLink.href = paper.url;
        paperLink.target = '_blank';
        paperLink.rel = 'noopener noreferrer';
        paperLink.className = 'text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1';
        paperLink.innerHTML = `
            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
            View Paper
        `;
        links.appendChild(paperLink);
    }

    if (paper.pdf_url) {
        const pdfLink = document.createElement('a');
        pdfLink.href = paper.pdf_url;
        pdfLink.target = '_blank';
        pdfLink.rel = 'noopener noreferrer';
        pdfLink.className = 'text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1';
        pdfLink.innerHTML = `
            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
            </svg>
            PDF
        `;
        links.appendChild(pdfLink);

        // Add chat about paper button
        const chatButton = document.createElement('button');
        chatButton.className = 'text-sm text-purple-600 hover:text-purple-800 flex items-center gap-1';
        chatButton.innerHTML = `
            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
            </svg>
            Chat About Paper
        `;
        chatButton.onclick = async () => {
            try {
                const response = await fetch(`/process-pdf?url=${encodeURIComponent(paper.pdf_url)}`);
                if (!response.ok) {
                    throw new Error('Failed to process PDF.');
                }

                const result = await response.json();
                if (result.error) {
                    alert(`Error processing PDF: ${result.error}`);
                } else {
                    if (result.chat_id) {
                        activeChatId = result.chat_id;
                        const paperTitle = paper.title || 'The paper'; // Ensure fallback if title is missing

                        addChatMessage(`"${paperTitle}" has been successfully loaded. You can now ask questions about its content.`, false);
                        // Scroll back to the top of the page
                        window.scrollTo({
                            top: 0,
                            behavior: 'smooth'
                        });
                    }
                }
            } catch (error) {
                alert(`An error occurred: ${error.message}`);
            }
    };
    links.appendChild(chatButton);
    }

    card.appendChild(titleLink);
    card.appendChild(metadata);
    card.appendChild(summary);
    card.appendChild(links);

    return card;
}

document.getElementById('sortBy').addEventListener('change', sortResults);
document.getElementById('sortOrder').addEventListener('click', () => {
    sortAscending = !sortAscending;
    sortResults();
    // Update sort icon
    document.getElementById('sortOrder').querySelector('svg').style.transform =
        sortAscending ? 'rotate(180deg)' : 'rotate(0deg)';
});

function sortResults() {
    const sortBy = document.getElementById('sortBy').value;
    const papersContainer = document.getElementById('papers');

    // Get ALL papers from our stored data
    const papers = Array.from(paperData.values());

    const sortedResults = papers.sort((a, b) => {
        let comparison = 0;
        switch(sortBy) {
            case 'citations':
                comparison = (b.citation_count || 0) - (a.citation_count || 0);
                break;
            case 'year':
                const dateA = a.publication_date ? new Date(a.publication_date) : new Date(0);
                const dateB = b.publication_date ? new Date(b.publication_date) : new Date(0);
                comparison = dateB - dateA;
                break;
            case 'relevance':
                comparison = (b.relevance || 0) - (a.relevance || 0);
                break;
        }
        return sortAscending ? -comparison : comparison;
    });

    // Clear and repopulate papers container
    papersContainer.innerHTML = '';
    sortedResults.forEach(paper => {
        if (paper && paper.paper_id) {
            const card = createPaperCard(paper);

            // If we already have a summary, update it immediately
            if (paper.summary) {
                const summaryElement = card.querySelector('.summary-placeholder');
                if (summaryElement) {
                    summaryElement.textContent = paper.summary;
                    summaryElement.classList.remove('animate-pulse', 'bg-gray-100');
                }
            }

            papersContainer.appendChild(card);
        }
    });
}

document.getElementById('chatButton').addEventListener('click', async () => {
    const query = document.getElementById('query').value.trim();
    if (!query) {
        showError('Please enter a question or topic');
        return;
    }
    await handleChat();
});

document.getElementById('searchButton').addEventListener('click', async () => {
    hideError();
    const searchButton = document.getElementById('searchButton');
    const loading = document.getElementById('loading');
    const results = document.getElementById('results');
    const query = document.getElementById('query').value.trim();
    const yearFilter = document.getElementById('yearFilter').value;

    if (!query) {
        showError('Please enter a search query');
        return;
    }
    // Disable the search button and update its text
    searchButton.disabled = true;
    searchButton.textContent = "Reload to Search Again";
    searchButton.classList.add('bg-gray-400', 'cursor-not-allowed');
    searchButton.classList.remove('bg-green-600', 'hover:bg-green-700');

    // Update original query display
    document.getElementById('originalQuery').textContent = query;

    loading.classList.remove('hidden');
    results.classList.add('hidden');
    const papersContainer = document.getElementById('papers');
    papersContainer.innerHTML = '';
    paperData.clear(); // Clear existing paper data

    const timelineSection = document.getElementById('timelineSection')
    timelineSection.classList.add('hidden');
    const timelineOutput = document.getElementById('timelineOutput')
    timelineOutput.innerHTML = '';
    const futureWorkSection = document.getElementById('futureWorkSection')
    const futureWorkOutput = document.getElementById('futureWorkOutput')
    futureWorkOutput.innerHTML = '';
    futureWorkSection.classList.add('hidden');


    try {
        const response = await fetch('/stream_search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, year_filter: yearFilter })
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const {value, done} = await reader.read();
            if (done) break;

            const lines = decoder.decode(value).split('\n');
            for (const line of lines) {
                if (!line) continue;
                const data = JSON.parse(line);

                switch (data.type) {
                    case 'refined_query':
                        document.getElementById('refinedQuery').textContent = data.data.join(', ');
                        results.classList.remove('hidden');
                        break;
                    case 'papers':
                        // Add new papers to paperData
                        data.data.forEach(paper => {
                            updatePaperData(paper);
                            // Only append to DOM if the card doesn't exist
                            if (!document.querySelector(`[data-paper-id="${paper.paper_id}"]`)) {
                                papersContainer.appendChild(createPaperCard(paper));
                            }
                        });
                        // Update total results count
                        document.getElementById('totalResults').textContent = paperData.size;
                        break;
                    case 'relevance':
                        const paper = paperData.get(data.data.paper_id);
                        if (paper) {
                            paper.relevance = data.data.relevance;
                            updatePaperData(paper);
                        }
                        sortResults();
                        break;
                    case 'summary':
                        updatePaperCard(data.data.paper_id, data.data.summary);
                        const existingPaper = paperData.get(data.data.paper_id);
                        if (existingPaper) {
                            existingPaper.summary = data.data.summary;
                            updatePaperData(existingPaper);
                        }
                        break;
                }
            }
        }
    } catch (error) {
        showError(error.message || 'An error occurred while searching');
    } finally {
        loading.classList.add('hidden');
    }
});


// Also add event listeners for the analysis tools
document.getElementById('timelineButton').addEventListener('click', generateTimeline);
document.getElementById('futureWorkButton').addEventListener('click', generateFutureWork);

// Add keypress event listener for the query input
document.getElementById('query').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        if (e.shiftKey) {
            // Shift + Enter triggers search
            document.getElementById('searchButton').click();
        } else {
            // Enter triggers chat
            handleChat();
        }
        e.preventDefault();
    }
});

// Call this when the page loads
const statusUpdates = initializeStatusUpdates();