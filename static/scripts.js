document.addEventListener("DOMContentLoaded", function () {
    let socket;
    let totalChunks = 0;
    let processedChunks = 0;

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

    function sendMessage(action, data) {
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
            startLoadingIndicator(); // Start the loading indicator
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
                updateProgress(message.data);
                break;
            case 'combined_summary':
                displayCombinedSummary(message.data);
                break;
            case 'cross_video_insights':
                displayCrossVideoInsights(message.data);
                break;
            case 'completed':
                displayFinalResults(message.data);
                stopLoadingIndicator(); // Stop the loading indicator
                break;
            case 'error':
                displayError(message.data);
                stopLoadingIndicator(); // Stop the loading indicator
                break;
            default:
                console.warn('Unknown message stage:', message.stage);
                stopLoadingIndicator(); // Stop the loading indicator
        }
    }

    function generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
            const r = (Math.random() * 16) | 0,
                v = c === 'x' ? r : (r & 0x3) | 0x8;
            return v.toString(16);
        });
    }

    function formatTime(seconds) {
        const date = new Date(0);
        date.setSeconds(seconds);
        return date.toISOString().substr(11, 8);
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

    function startProgressBar(total) {
        const progressBar = document.getElementById('progress-bar');
        progressBar.value = 0;
        progressBar.max = total;
        progressBar.removeAttribute('hidden');
        totalChunks = total;
        processedChunks = 0;
    }

    function updateProgress(data) {
        const progressInsights = document.getElementById('progress-insights');
        const progressBar = document.getElementById('progress-bar');

        if (data.chunk_summary) {
            const insight = document.createElement('div');
            insight.innerHTML = `
                <strong>Video ID:</strong> ${data.video_id}<br>
                <strong>Chunk:</strong> ${data.chunk_index} of ${data.total_chunks}<br>
                <strong>Summary:</strong> ${data.chunk_summary.full_summary || 'N/A'}<br>`;
            progressInsights.appendChild(insight);

            processedChunks += 1;
            if (totalChunks && processedChunks <= totalChunks) {
                progressBar.value = processedChunks;
            }
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
        const progressSection = document.getElementById('progress-section');
        const analysisResults = document.getElementById('analysis-results');

        progressSection.style.display = 'none';
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
            li.classList.add('list-group-item', 'list-group-item-danger');
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

    function startLoadingIndicator() {
        const statusElement = document.getElementById('status');
        if (statusElement) {
            statusElement.classList.add('loading');
        }
    }

    function stopLoadingIndicator() {
        const statusElement = document.getElementById('status');
        if (statusElement) {
            statusElement.classList.remove('loading');
        }
    }

    const getVideosCategoryTextButton = document.getElementById('get-videos-category-text-button');
    if (getVideosCategoryTextButton) {
        getVideosCategoryTextButton.addEventListener('click', function () {
            const categoryIdInput = document.getElementById('category-id-text-input');
            const categoryId = categoryIdInput.value === "" ? null : categoryIdInput.value;
            const freeTextInput = document.getElementById('free-text-input');
            const freeText = freeTextInput.value === "" ? null : freeTextInput.value;
            sendMessage('get_videos', { categoryId, freeText });
        });
    } else {
        console.error('Search videos button not found');
    }

    const analyzeVideosButton = document.getElementById('analyze-videos-button');
    if (analyzeVideosButton) {
        analyzeVideosButton.addEventListener('click', function () {
            const videoIdsInput = document.getElementById('video-ids-input');
            if (videoIdsInput) {
                const selectedVideos = videoIdsInput.value.split(',').map(id => id.trim());
                startProgressBar(selectedVideos.length); // Start the progress bar animation immediately
                sendMessage('analyze_videos', { selectedVideos });
            } else {
                console.error('Video IDs input not found');
            }
        });
    } else {
        console.error('Analyze Videos button not found');
    }
});
