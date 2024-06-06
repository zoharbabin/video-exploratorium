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
            showAccordion('search-card');
            openAccordionsByIds('search-card');
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
    
    const reloadFollowupQuestionsButton = document.getElementById('reload-followup-questions');
    if (reloadFollowupQuestionsButton) {
        reloadFollowupQuestionsButton.originalText = reloadFollowupQuestionsButton.textContent;
        reloadFollowupQuestionsButton.addEventListener('click', function () {
            generateFollowupQuestions(transcripts);
        });
    } else {
        console.error('Reload Follow-up Questions button not found');
    }

    function generateFollowupQuestions(videoTranscripts) {
        showFollowupQuestionsLoading();
        sendMessage('generate_followup_questions', { transcripts: videoTranscripts });
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
                generateFollowupQuestions(transcripts);
                break;
            case 'followup_questions':
                const followupQuestions = message.data.questions;
                displayFollowupQuestions(followupQuestions);
                stopLoadingIndicator();
                openAccordionsByIds('followup-questions-card');
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

    function displayFollowupQuestions(questions) {
        const followupQuestionsContainer = document.getElementById('followup-questions-content');
        if (followupQuestionsContainer) {
            followupQuestionsContainer.innerHTML = '<h5>Suggested Follow-up Questions</h5>';
            const buttonsContainer = document.createElement('div');
            buttonsContainer.className = 'suggestions-buttons-container';
            questions.forEach((question) => {
                const button = document.createElement('button');
                button.className = 'suggestion-button';
                button.setAttribute('data-question', question.question);
                button.textContent = question.question;
                button.addEventListener('click', function () {
                    const questionText = this.getAttribute('data-question');
                    sendSuggestionToChat(questionText);
                });
                buttonsContainer.appendChild(button);
            });
            followupQuestionsContainer.appendChild(buttonsContainer);
            showAccordion('followup-questions-card');
        }
    }
    
    function sendSuggestionToChat(question) {
        displayChatMessage('You', question);
        sendMessage('ask_question', { question: question, analysisResults: analysisResults, transcripts: transcripts, chat_history: chatHistory }, sendChatButton);
    }   
    
    function showFollowupQuestionsLoading() {
        const followupQuestionsContainer = document.getElementById('followup-questions-content');
        if (followupQuestionsContainer) {
            followupQuestionsContainer.innerHTML = '<span aria-busy="true">Generating suggestions...</span>';
            showAccordion('followup-questions-card');
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
                            ${video.entry_ms_duration ? `<li><small>Duration: ${formatTime((video.entry_ms_duration/1000))}</small></li>` : ''}
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
    const categoryIdInput = document.getElementById('category-id-text-input');
    const freeTextInput = document.getElementById('free-text-input');
    function handleGetVideos() {
        const categoryId = categoryIdInput.value === "" ? null : categoryIdInput.value;
        const freeText = freeTextInput.value === "" ? null : freeTextInput.value;
        sendMessage('get_videos', { categoryId, freeText }, getVideosCategoryTextButton);
    }
    if (getVideosCategoryTextButton) {
        getVideosCategoryTextButton.originalText = getVideosCategoryTextButton.textContent;
        getVideosCategoryTextButton.addEventListener('click', handleGetVideos);
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

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Enter') {
            if (document.activeElement === categoryIdInput || document.activeElement === freeTextInput) {
                event.preventDefault();
                handleGetVideos();
            } else if (document.activeElement === chatInput) {
                event.preventDefault();
                sendChatButton.click();            
            }
        }
    });

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
        let currentListType = null;

        lines.forEach(line => {
            const trimmedLine = line.trim();
            if (trimmedLine.match(/^\d+\.\s+/) || trimmedLine.startsWith('* ')) {
                // Determine list type
                const isOrderedList = trimmedLine.match(/^\d+\.\s+/);
                const listType = isOrderedList ? 'ol' : 'ul';

                // Create a new list if the list type has changed or there is no current list
                if (!currentList || currentListType !== listType) {
                    currentList = document.createElement(listType);
                    container.appendChild(currentList);
                    currentListType = listType;
                }

                // Create a list item
                const li = document.createElement('li');
                li.textContent = trimmedLine.replace(/^\d+\.\s*/, '').replace(/^\*\s*/, '');
                currentList.appendChild(li);
            } else if (trimmedLine === '') {
                // Reset the list if an empty line is encountered
                currentList = null;
                currentListType = null;
            } else {
                // Create a paragraph for any other text
                if (currentList) {
                    currentList = null;
                    currentListType = null;
                }
                const p = document.createElement('p');
                p.textContent = trimmedLine;
                container.appendChild(p);
            }
        });

        // Append "LLM:" to the answer text
        const llmIndicator = document.createElement('strong');
        llmIndicator.innerText = 'LLM:';
        container.prepend(llmIndicator);

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
