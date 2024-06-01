document.addEventListener("DOMContentLoaded", function () {
    let socket;
    let currentButton = null;
    const chatSection = document.getElementById('chat-section');
    const chatContainer = document.getElementById('chat-container');
    const chatMessages = document.getElementById('chat-messages');
    const chatInput = document.getElementById('chat-input');
    let analysisResults = null;
    let transcripts = null;

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

    connectWebSocket();

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
                displayFinalResults(message.data);
                stopLoadingIndicator();
                closeAllAccordions();
                openAccordionsByIds('individual-videos-analysis-results', 'cross-video-insights-card', 'chat-section');
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
                const li = document.createElement('li');
                li.innerHTML = `
                    ${generateThumbnail(pid, video.entry_id)}
                    <div>
                        <strong>${video.entry_name}</strong> (${video.entry_id})<br>
                        <small>${video.entry_description}</small>
                        <br><small>Zoom Recording ID: ${video.entry_reference_id}</small>
                    </div>`;
                videoList.appendChild(li);
            });
            showAccordion('videos-card');
        }
    }

    function generateThumbnail(pid, entry_id, time_seconds = 0) {
        return `<img src="https://cfvod.kaltura.com/p/${pid}/sp/${pid}00/thumbnail/entry_id/${entry_id}/width/80/type/2/bgcolor/000000?time=${time_seconds}" alt="Thumbnail">`;
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
            showAccordion('cross-video-insights-card');
        } else {
            hideAccordion('cross-video-insights-card');
        }
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
                        ${generateThumbnail(pid, result.entry_id, section.start_time)}
                        <strong>${section.title}</strong>: ${section.summary}
                        <br><small>Start: ${section.start_sentence} (Time: ${formatTime(section.start_time)})</small>
                    </li>`;
            });
            resultHTML += '</ul>';
        }

        if (result.insights && result.insights.length > 0) {
            resultHTML += '<h5>Insights</h5><ul>';
            result.insights.forEach(insight => {
                resultHTML += `<li>${insight.text} (Time: ${formatTime(insight.start_time)})</li>`;
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

    const analyzeVideosButton = document.getElementById('analyze-videos-button');
    if (analyzeVideosButton) {
        analyzeVideosButton.originalText = analyzeVideosButton.textContent;
        analyzeVideosButton.addEventListener('click', function () {
            const videoIdsInput = document.getElementById('video-ids-input');
            if (videoIdsInput) {
                const selectedVideos = videoIdsInput.value.split(',').map(id => id.trim());
                sendMessage('analyze_videos', { selectedVideos }, analyzeVideosButton);
            } else {
                console.error('Video IDs input not found');
            }
        });
    } else {
        console.error('Analyze Videos button not found');
    }

    const sendChatButton = document.getElementById('send-chat-button');
    if (sendChatButton) {
        sendChatButton.originalText = sendChatButton.textContent;
        sendChatButton.addEventListener('click', function () {
            const question = chatInput.value.trim();
            if (question) {
                displayChatMessage('You', question);
                sendMessage('ask_question', { question, analysisResults, transcripts }, sendChatButton);
                chatInput.value = ''; // Clear the input
            }
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
        }
    }

    function hideAccordion(id) {
        const accordion = document.getElementById(id);
        if (accordion) {
            accordion.style.display = 'none';
            accordion.removeAttribute('open');
        }
    }

    function displayChatMessage(sender, message) {
        const messageElement = document.createElement('div');
        messageElement.className = 'chat-message';
        messageElement.innerHTML = `<strong>${sender}:</strong> ${message}`;
        chatMessages.appendChild(messageElement);
        chatContainer.scrollTop = chatContainer.scrollHeight; // Scroll to the bottom
    }
});

