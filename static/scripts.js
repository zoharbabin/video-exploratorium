document.addEventListener("DOMContentLoaded", function () {
    let socket;
    let currentButton = null; // Track the current button being processed

    function connectWebSocket() {
        socket = new WebSocket('wss://fyocljsr02.execute-api.us-east-1.amazonaws.com/vidbot/');
        
        socket.onopen = function () {
            showStatus('Connected to the server', 'success');
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
            showStatus('Message sent to the server...', 'info');
            startLoadingIndicator(button); // Start the loading indicator and change button state
        } else {
            console.error('WebSocket is not open. Ready state: ' + socket.readyState);
        }
    }

    function handleServerMessage(message) {
        showStatus('Response received from the server', 'success');

        switch (message.stage) {
            case 'videos':
                displayVideos(message.data);
                break;
            case 'chunk_progress':
                // Handle chunk progress if needed
                break;
            case 'combined_summary':
                displayCombinedSummary(message.data);
                break;
            case 'cross_video_insights':
                displayCrossVideoInsights(message.data);
                break;
            case 'completed':
                displayFinalResults(message.data);
                stopLoadingIndicator(); // Stop the loading indicator and revert button state
                break;
            case 'error':
                displayError(message.data);
                stopLoadingIndicator(); // Stop the loading indicator and revert button state
                break;
            default:
                console.warn('Unknown message stage:', message.stage);
                stopLoadingIndicator(); // Stop the loading indicator and revert button state
        }
    }

    function generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
            const r = (Math.random() * 16) | 0,
                v = c === 'x' ? r : (r & 0x3) | 0x8;
            return v.toString(16);
        });
    }

    function displayVideos(videos) {
        const videoList = document.getElementById('video-list-items');
        const { pid } = getUrlParams();
        if (videoList) {
            videoList.innerHTML = '';
            videos.forEach(video => {
                const li = document.createElement('li');
                li.innerHTML = `
                    <img src="https://cfvod.kaltura.com/p/${pid}/sp/${pid}00/thumbnail/entry_id/${video.entry_id}/width/80/type/2/bgcolor/000000" alt="Thumbnail">
                    <div>
                        <strong>${video.entry_name}</strong> (${video.entry_id})<br>
                        <small>${video.entry_description}</small>
                        <br><small>Zoom Recording ID: ${video.entry_reference_id}</small>
                    </div>`;
                videoList.appendChild(li);
            });
            document.getElementById('videos-card').style.display = 'block';
        }
    }

    function displayCombinedSummary(data) {
        const combinedSummaryContent = document.getElementById('combined-summary-content');
        if (combinedSummaryContent) {
            combinedSummaryContent.innerHTML = `
                <h4>Full Summary</h4>
                <p>${data.full_summary}</p>
                ${data.sections.length > 0 ? `<h4>Sections</h4><ul>${data.sections.map(section => `<li><strong>${section.title}</strong>: ${section.summary}<br><small>${section.start_sentence}</small></li>`).join('')}</ul>` : ''}
                ${data.insights.length > 0 ? `<h4>Insights</h4><ul>${data.insights.map(insight => `<li>${insight.text}</li>`).join('')}</ul>` : ''}
                ${data.people.length > 0 ? `<h4>People</h4><ul>${data.people.map(person => `<li>${person.name}</li>`).join('')}</ul>` : ''}
                ${data.primary_topics.length > 0 ? `<h4>Primary Topics</h4><ul>${data.primary_topics.map(topic => `<li>${topic}</li>`).join('')}</ul>` : ''}`;
        }
    }

    function displayCrossVideoInsights(data) {
        const insightsContent = document.getElementById('cross-video-insights-content');
        if (insightsContent) {
            insightsContent.innerHTML = `
                ${data.shared_insights && data.shared_insights.length > 0 ? `<h4>Shared Insights</h4><ul>${data.shared_insights.map(insight => `<li>${insight}</li>`).join('')}</ul>` : ''}
                ${data.common_themes && data.common_themes.length > 0 ? `<h4>Common Themes</h4><ul>${data.common_themes.map(theme => `<li>${theme}</li>`).join('')}</ul>` : ''}
                ${data.opposing_views && data.opposing_views.length > 0 ? `<h4>Opposing Views</h4><ul>${data.opposing_views.map(view => `<li>${view}</li>`).join('')}</ul>` : ''}
                ${data.sentiments && data.sentiments.length > 0 ? `<h4>Sentiments</h4><ul>${data.sentiments.map(sentiment => `<li>${sentiment}</li>`).join('')}</ul>` : ''}`;
            document.getElementById('cross-video-insights-card').style.display = 'block';
        } else {
            document.getElementById('cross-video-insights-card').style.display = 'none';
        }
    }

    function displayFinalResults(data) {
        const analysisResults = document.getElementById('analysis-results');
        analysisResults.style.display = 'block';

        const combinedSummaryContent = document.getElementById('combined-summary-content');
        combinedSummaryContent.innerHTML = '';
        data.individual_results.forEach(result => {
            displayCombinedSummary(result);
        });

        if (data.cross_video_insights) {
            displayCrossVideoInsights(data.cross_video_insights);
        } else {
            document.getElementById('cross-video-insights-card').style.display = 'none';
        }
    }

    function displayError(error) {
        const errorList = document.getElementById('error-list');
        if (errorList) {
            const li = document.createElement('li');
            li.innerText = `Error: ${error}`;
            errorList.appendChild(li);
            document.getElementById('errors-card').style.display = 'block';
        }
    }

    function showStatus(message, statusClass) {
        const statusElement = document.getElementById('status');
        if (statusElement) {
            statusElement.innerText = message;
            statusElement.className = `alert ${statusClass}`;
        }
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
});
