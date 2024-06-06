document.addEventListener("DOMContentLoaded", function () {
    let socket;
    let currentButton = null;
    const chatSection = document.getElementById('chat-section');
    const chatContainer = document.getElementById('chat-container');
    const chatMessages = document.getElementById('chat-messages');
    const chatInput = document.getElementById('chat-input');
    let analysisResults = null;
    let transcripts = null;
    let chatHistory = []; // Array to hold chat messages

    function connectWebSocket() {
        socket = new WebSocket('wss://fyocljsr02.execute-api.us-east-1.amazonaws.com/vidbot/');
        showStatus('ᯤ connecting...', 'progress');

        socket.onopen = function () {
            showStatus('ထ', 'success');
        };

        socket.onclose = function () {
            showStatus('Disconnected from the server. Reconnecting...', 'danger');
            setTimeout(connectWebSocket, 5000); // Try to reconnect every 5 seconds
        };

        socket.onerror = function (error) {
            console.error('WebSocket Error:', error);
            showStatus('WebSocket Error', 'danger');
        };

        socket.onmessage = function (event) {
            const message = JSON.parse(event.data);
            handleServerMessage(message);
        };
    }

    function showStatus(message, statusClass) {
        const statusElement = document.getElementById('status');
        if (statusElement) {
            statusElement.innerText = message;
            statusElement.className = `status ${statusClass}`;
        }
    }

    function getUrlParams() {
        const params = new URLSearchParams(window.location.search);
        return {
            pid: params.get('pid'),
            ks: params.get('ks')
        };
    }

    function sendMessage(action, data, button) {
        const { pid, ks } = getUrlParams();
        if (!pid || !ks) {
            console.error('PID and KS parameters are required');
            showStatus('pid and ks URL parameters are required!', 'danger');
            return;
        }

        const message = {
            action: action,
            request_id: generateUUID(),
            headers: {
                'X-Authentication': `${pid}:${ks}`
            },
            ...data
        };

        if (socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify(message));
            startLoadingIndicator(button); // Start the loading indicator and change button state
        } else {
            console.error('WebSocket is not open. Ready state: ' + socket.readyState);
        }
    }

    function handleServerMessage(message) {
        switch (message.stage) {
            case 'videos':
                // Handle search videos list results
                displayVideos(message.data);
                stopLoadingIndicator();
                closeAllAccordions();
                openAccordionsByIds('videos-card');
                break;
            case 'chunk_progress':
                // Handle gradual analysis progress: a chunk of a single video complete
                break;
            case 'combined_summary':
                // Handle gradual analysis progress: single video all chunks complete
                break;
            case 'cross_video_insights':
                // Handle gradual analysis progress: cross videos complete (combined summary)
                break;
            case 'completed':
                // Handle final analysis results (the whole process is complete and full results are available):
                let crossIncluded = displayFinalResults(message.data);
                stopLoadingIndicator();
                closeAllAccordions();
                if (crossIncluded)
                    openAccordionsByIds('individual-videos-analysis-results', 'cross-video-insights-card', 'chat-section');
                else
                    openAccordionsByIds('individual-videos-analysis-results', 'chat-section');
                analysisResults = message.data.individual_results;
                transcripts = message.data.transcripts;
                break;
            case 'error':
                displayError(message.data);
                stopLoadingIndicator();
                closeAllAccordions();
                openAccordionsByIds('errors-card');
                break;
            case 'chat_response':
                displayChatMessage('LLM', message.data.answer);
                stopLoadingIndicator();
                openAccordionsByIds('chat-section');
                chatHistory.push({ sender: 'LLM', message: message.data.answer });
                break;
            default:
                if (message.hasOwnProperty('stage')) {
                    console.warn('Unhandled message stage sent on the websocket:', message.stage);
                } else {
                    console.warn('Unhandled message on the websocket:', message.message);
                }
        }
    }

    function generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
            const r = (Math.random() * 16) | 0,
                v = c === 'x' ? r : (r & 0x3) | 0x8;
            return v.toString(16);
        });
    }

    function displayError(errorData) {
        const errorsCard = document.getElementById('errors-card');
        const errorList = document.getElementById('error-list');
    
        if (errorsCard && errorList) {
            let errorHTML = '';
    
            if (typeof errorData === 'string') {
                errorHTML += `<li>${errorData}</li>`;
            } else if (typeof errorData === 'object') {
                for (const key in errorData) {
                    if (errorData.hasOwnProperty(key)) {
                        errorHTML += `<li><strong>${key}:</strong> ${errorData[key]}</li>`;
                    }
                }
            } else {
                errorHTML += '<li>An unknown error occurred.</li>';
            }
    
            errorList.innerHTML = errorHTML;
            showAccordion('errors-card');
        } else {
            console.error('Error card or error list element not found');
        }
    }    

    function displayVideos(videos) {
        const videoList = document.getElementById('video-list-items');
        const { pid } = getUrlParams();
        if (videoList) {
            videoList.innerHTML = '';
            videos.forEach(video => {
                const videoItem = document.createElement('div');
                videoItem.id = `videoItem-${video.entry_id}`;
                videoItem.innerHTML = `
                    <div>    
                        <input type="checkbox" class="video-checkbox" data-entry-id="${video.entry_id}">
                    </div>
                    <div class="thumbnail-container">
                        ${generateThumbnail(pid, video.entry_id, 0, 120, true)}
                    </div>
                    <div>
                        <ul>
                            <li><h6>${video.entry_name} <small>(${video.entry_id})</small></h6></li>
                            ${video.entry_description ? `<li>${truncateWithEllipsis(strip(video.entry_description), 240)}</li>` : ''}
                            ${video.entry_reference_id ? `<li><small>RefID: ${video.entry_reference_id}</small></li>` : ''}
                        </ul>
                    </div>`;
                videoList.appendChild(videoItem);
            });
            showAccordion('videos-card');
        }
    }

    function strip(html) {
        const doc = new DOMParser().parseFromString(html, 'text/html');
        return doc.body.textContent || "";
    }

    function generateThumbnail(pid, entry_id, time_seconds = 0, width = 120, no_time = false) {
        return `<img class="thumbnail-img" src="https://cfvod.kaltura.com/p/${pid}/sp/${pid}00/thumbnail/entry_id/${entry_id}/width/${width}/type/2/bgcolor/000000/quality/85/${no_time ? '' : 'vid_sec/' + time_seconds}" alt="Thumbnail of ${entry_id} at ${time_seconds} sec">`;
    }

    function truncateWithEllipsis(text, maxLength = 24) {
        if (text.length <= maxLength) {
            return text;
        }
        
        let truncated = text.slice(0, maxLength);
        const lastPeriodIndex = truncated.lastIndexOf('.');
        const lastSpaceIndex = truncated.lastIndexOf(' ');
    
        if (lastPeriodIndex !== -1 && lastPeriodIndex + 1 <= maxLength) {
            return truncated.slice(0, lastPeriodIndex + 1) + '...';
        }
        
        if (lastSpaceIndex !== -1 && lastSpaceIndex <= maxLength) {
            return truncated.slice(0, lastSpaceIndex) + '...';
        }
        
        // If no period or space is found, cut off at the max length, ensuring it does not cut in the middle of a word
        truncated = text.slice(0, maxLength);
        const lastWordBoundaryIndex = truncated.lastIndexOf(' ');
        if (lastWordBoundaryIndex !== -1) {
            return truncated.slice(0, lastWordBoundaryIndex) + '...';
        }
        
        return truncated + '...';
    }

    function formatTime(seconds) {
        const h = Math.floor(seconds / 3600).toString().padStart(2, '0');
        const m = Math.floor(seconds % 3600 / 60).toString().padStart(2, '0');
        const s = Math.floor(seconds % 60).toString().padStart(2, '0');
        return `${h}:${m}:${s}`;
    }

    function displayFinalResults(data) {
        const analysisResults = document.getElementById('individual-videos-analysis-results');
        showAccordion('individual-videos-analysis-results');

        const navbar = document.getElementById('individual-videos-navbar');
        navbar.innerHTML = '<ul><li><strong>Choose an entry:</strong></li></ul><ul></ul>';

        data.individual_results.forEach((result, index) => {
            const li = document.createElement('li');
            li.innerHTML = `<button class="secondary" data-index="${index}">${result.entry_id}</button>`;
            navbar.querySelector('ul:nth-child(2)').appendChild(li);
        });

        navbar.querySelectorAll('button').forEach(button => {
            button.addEventListener('click', function () {
                const index = this.getAttribute('data-index');
                displayVideoResult(data.individual_results[index]);
            });
        });

        // Display the first video result by default
        displayVideoResult(data.individual_results[0]);

        if (data.cross_video_insights) {
            const crossVideoInsights = data.cross_video_insights;
            let insightsHTML = '<h4>Cross Video Insights</h4>';

            if (crossVideoInsights.shared_insights && crossVideoInsights.shared_insights.length > 0) {
                insightsHTML += '<h5>Shared Insights</h5><ul>';
                crossVideoInsights.shared_insights.forEach(insight => {
                    insightsHTML += `<li>${insight}</li>`;
                });
                insightsHTML += '</ul>';
            }

            if (crossVideoInsights.common_themes && crossVideoInsights.common_themes.length > 0) {
                insightsHTML += '<h5>Common Themes</h5><ul>';
                crossVideoInsights.common_themes.forEach(theme => {
                    insightsHTML += `<li>${theme}</li>`;
                });
                insightsHTML += '</ul>';
            }

            if (crossVideoInsights.opposing_views && crossVideoInsights.opposing_views.length > 0) {
                insightsHTML += '<h5>Opposing Views</h5><ul>';
                crossVideoInsights.opposing_views.forEach(view => {
                    insightsHTML += `<li>${view}</li>`;
                });
                insightsHTML += '</ul>';
            }

            if (crossVideoInsights.sentiments && crossVideoInsights.sentiments.length > 0) {
                insightsHTML += '<h5>Sentiments</h5><ul>';
                crossVideoInsights.sentiments.forEach(sentiment => {
                    insightsHTML += `<li>${sentiment}</li>`;
                });
                insightsHTML += '</ul>';
            }

            document.getElementById('cross-video-insights-content').innerHTML = insightsHTML;
            return true;
        } else {
            return false;
        }
    }

    const analyzeSelectedVideosButton = document.getElementById('analyze-selected-videos-button');
    if (analyzeSelectedVideosButton) {
        analyzeSelectedVideosButton.originalText = analyzeSelectedVideosButton.textContent;
        analyzeSelectedVideosButton.addEventListener('click', function () {
            const selectedVideos = Array.from(document.querySelectorAll('.video-checkbox:checked')).map(checkbox => checkbox.getAttribute('data-entry-id'));
            if (selectedVideos.length === 0) {
                alert('Please select at least one video to analyze.');
                return;
            }
            sendMessage('analyze_videos', { selectedVideos }, this);
        });
    } else {
        console.error('Analyze Selected Videos button not found');
    }

    function displayVideoResult(result) {
        const { pid } = getUrlParams();
        let resultHTML = `
            <h4>Video Entry: ${result.entry_id}</h4>
            <p><strong>Full Summary:</strong> ${result.full_summary}</p>
        `;

        if (result.sections && result.sections.length > 0) {
            resultHTML += '<h5>Sections</h5><ul>';
            result.sections.forEach(section => {
                resultHTML += `
                    <li>
                        ${generateThumbnail(pid, result.entry_id, (section.start_time / 1000))}
                        <strong>${section.title}</strong>${section.summary}
                        <br><small>Start: ${section.start_sentence} (Time: ${formatTime((section.start_time / 1000))})</small>
                    </li>`;
            });
            resultHTML += '</ul>';
        }

        if (result.insights && result.insights.length > 0) {
            resultHTML += '<h5>Insights</h5><ul>';
            result.insights.forEach(insight => {
                resultHTML += `<li>${insight.text} (Time: ${formatTime((insight.start_time / 1000))})</li>`;
            });
            resultHTML += '</ul>';
        }

        if (result.people && result.people.length > 0) {
            resultHTML += '<h5>People</h5><ul>';
            result.people.forEach(person => {
                resultHTML += `<li>${person.name}</li>`;
            });
            resultHTML += '</ul>';
        }

        if (result.primary_topics && result.primary_topics.length > 0) {
            resultHTML += '<h5>Primary Topics</h5><ul>';
            result.primary_topics.forEach(topic => {
                resultHTML += `<li>${topic}</li>`;
            });
            resultHTML += '</ul>';
        }

        const summaryContent = document.getElementById('individual-videos-summary-content');
        summaryContent.innerHTML = resultHTML;
    }

    function startLoadingIndicator(button) {
        currentButton = button;
        if (currentButton) {
            currentButton.setAttribute('aria-busy', 'true');
            currentButton.textContent = 'Please wait…';
        }
    }

    function stopLoadingIndicator() {
        if (currentButton) {
            currentButton.removeAttribute('aria-busy');
            currentButton.textContent = currentButton.originalText;
            currentButton = null;
        }
    }

    const getVideosCategoryTextButton = document.getElementById('get-videos-category-text-button');
    if (getVideosCategoryTextButton) {
        getVideosCategoryTextButton.originalText = getVideosCategoryTextButton.textContent;
        getVideosCategoryTextButton.addEventListener('click', function () {
            const categoryIdInput = document.getElementById('category-id-text-input');
            const categoryId = categoryIdInput.value === "" ? null : categoryIdInput.value;
            const freeTextInput = document.getElementById('free-text-input');
            const freeText = freeTextInput.value === "" ? null : freeTextInput.value;
            sendMessage('get_videos', { categoryId, freeText }, getVideosCategoryTextButton);
        });
    } else {
        console.error('Search videos button not found');
    }

    const sendChatButton = document.getElementById('send-chat-button');
    if (sendChatButton) {
        sendChatButton.originalText = sendChatButton.textContent;
        sendChatButton.addEventListener('click', function () {
            const question = chatInput.value.trim();
            displayChatMessage('You', question);
            sendMessage('ask_question', { question: question, analysisResults: analysisResults, transcripts: transcripts, chat_history: chatHistory }, sendChatButton);
            chatInput.value = ''; // Clear the input field
        });
    } else {
        console.error('Send Chat button not found');
    }
    
    function closeAllAccordions() {
        document.querySelectorAll('details').forEach(detail => {
            detail.removeAttribute('open');
        });
    }

    function openAccordionsByIds(...ids) {
        ids.forEach(id => {
            showAccordion(id);
        });
    }

    function showAccordion(id) {
        const accordion = document.getElementById(id);
        if (accordion) {
            accordion.style.display = 'block';
            accordion.setAttribute('open', 'open');
            
            // Find the next <hr /> element and set its display to 'block'
            const nextHr = accordion.nextElementSibling;
            if (nextHr && nextHr.tagName.toLowerCase() === 'hr') {
                nextHr.style.display = 'block';
            }
        }
    }    

    function hideAccordion(id) {
        const accordion = document.getElementById(id);
        if (accordion) {
            accordion.style.display = 'none';
            accordion.removeAttribute('open');
    
            // Find the next <hr /> element and set its display to 'none'
            const nextHr = accordion.nextElementSibling;
            if (nextHr && nextHr.tagName.toLowerCase() === 'hr') {
                nextHr.style.display = 'none';
            }
        }
    }    

    function displayChatMessage(sender, message) {
        if (sender === 'LLM') {
            renderChatResponse(message);
        } else {
            const messageElement = document.createElement('div');
            messageElement.className = 'chat-message';
            messageElement.innerHTML = `<strong>${sender}:</strong> ${message}`;
            chatMessages.appendChild(messageElement);
            chatContainer.scrollTop = chatContainer.scrollHeight; // Scroll to the bottom
            chatHistory.push({ sender: sender, message: message }); // Add message to chat history
        }
    }

    function renderChatResponse(answerText) {
        // Create a container for the rendered content
        const container = document.createElement('div');
        container.className = 'chat-response';

        // Split the answer text into lines
        const lines = answerText.split('\n');

        // Determine the content type and render appropriately
        let currentList = null;

        lines.forEach(line => {
            const trimmedLine = line.trim();
            if (trimmedLine.startsWith('1. ') || trimmedLine.startsWith('* ')) {
                // Create an ordered list or unordered list
                if (!currentList) {
                    currentList = trimmedLine.startsWith('1. ') ? document.createElement('ol') : document.createElement('ul');
                    container.appendChild(currentList);
                }
                // Create a list item
                const li = document.createElement('li');
                li.textContent = trimmedLine.replace(/^\d+\.\s*/, '').replace(/^\*\s*/, '');
                currentList.appendChild(li);
            } else if (trimmedLine === '') {
                // Reset the list if an empty line is encountered
                currentList = null;
            } else {
                // Create a paragraph for any other text
                if (currentList) {
                    currentList = null;
                }
                const p = document.createElement('p');
                p.textContent = trimmedLine;
                container.appendChild(p);
            }
        });

        // append "LLM:" to the answer text
        const llm_indicator = document.createElement('strong');
        llm_indicator.text = 'LLM:';
        container.prepend(llm_indicator);
        // Append the rendered content to chat messages
        chatMessages.appendChild(container);
        chatContainer.scrollTop = chatContainer.scrollHeight; // Scroll to the bottom
    }

    hideAccordion('videos-card');
    hideAccordion('progress-section');
    hideAccordion('individual-videos-analysis-results');
    hideAccordion('cross-video-insights-card');
    hideAccordion('chat-section');
    hideAccordion('errors-card');
    closeAllAccordions();
    connectWebSocket();
});
