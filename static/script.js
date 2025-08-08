let currentTravelPlan = "";
let currentBudget = 0;
let currentTravelers = 1;
let currentInterests = [];
let currentIncludeFlights = false;
let currentSource = "";
let currentDestination = "";
let currentStartDate = "";

document.getElementById('travelForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    // Show loading spinner
    document.getElementById('loading').style.display = 'block';
    document.getElementById('result').style.display = 'none';

    // Get form values
    const source = document.getElementById('source').value;
    const destination = document.getElementById('destination').value;
    const startDate = document.getElementById('startDate').value;
    const endDate = document.getElementById('endDate').value;
    const budget = parseFloat(document.getElementById('budget').value);
    const numTravelers = parseInt(document.getElementById('numTravelers').value);
    const interests = document.getElementById('interests').value.split(',').map(interest => interest.trim());
    const includeFlights = document.getElementById('includeFlights') ? document.getElementById('includeFlights').checked : false;

    try {
        const response = await fetch('http://localhost:8000/plan-trip', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                source,
                destination,
                start_date: startDate,
                end_date: endDate,
                budget,
                num_travelers: numTravelers,
                interests,
                include_flights: includeFlights
            }),
        });

        const data = await response.json();

        if (data.success) {
            // Display the result
            console.log("Travel Plan Response:", data.plan);
            document.getElementById('planContent').innerHTML = (typeof marked !== 'undefined' && marked.parse) ? marked.parse(data.plan) : `<pre>${data.plan}</pre>`;
            document.getElementById('chatMessages').innerHTML = '';
            currentTravelPlan = data.plan;
            // Store extra fields for chat
            currentBudget = budget;
            currentTravelers = numTravelers;
            currentInterests = interests;
            currentIncludeFlights = includeFlights;
            currentSource = source;
            currentDestination = destination;
            currentStartDate = startDate;
            document.getElementById('chatBox').classList.remove('hidden');
            // Handle flight details
            const flightDetailsDiv = document.getElementById('flightDetails');
            if (data.flight_details) {
                document.getElementById('flightContent').innerHTML = marked.parse(data.flight_details);
                flightDetailsDiv.classList.remove('hidden');
            } else {
                flightDetailsDiv.classList.add('hidden');
            }
            const resultDiv = document.getElementById('result');
            resultDiv.style.display = 'block';
            resultDiv.classList.remove('hidden');
        } else {
            // Show error in the result area
            document.getElementById('planContent').innerHTML = `<span style='color:red;'>${data.error ? data.error : 'Error generating travel plan. Please try again.'}</span>`;
            const resultDiv = document.getElementById('result');
            resultDiv.style.display = 'block';
            resultDiv.classList.remove('hidden');
        }
    } catch (error) {
        alert('Error connecting to the server: ' + error.message);
    } finally {
        // Hide loading spinner
        document.getElementById('loading').style.display = 'none';
    }
});

async function sendMessage() {
    const chatInput = document.getElementById('chatInput');
    const message = chatInput.value.trim();
    if (!message) return;

    // Clear input
    chatInput.value = '';

    // Add user message to chat
    addMessageToChat(message, true);

    try {
        console.log("Chat payload:", {
            question: message,
            travel_plan: currentTravelPlan,
            budget: currentBudget,
            travelers: currentTravelers,
            interests: currentInterests,
            include_flights: currentIncludeFlights,
            source: currentSource,
            destination: currentDestination,
            start_date: currentStartDate
        });
        const response = await fetch('http://localhost:8000/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                question: message,
                travel_plan: currentTravelPlan,
                budget: currentBudget,
                travelers: currentTravelers,
                interests: currentInterests,
                include_flights: currentIncludeFlights,
                source: currentSource,
                destination: currentDestination,
                start_date: currentStartDate
            }),
        });

        const data = await response.json();
        if (response.ok) {
            // Add AI response to chat
            addMessageToChat(data.response, false);
        } else {
            addMessageToChat("Sorry, I couldn't process your question. Please try again.", false);
        }
    } catch (error) {
        addMessageToChat("Error connecting to the server. Please try again.", false);
    }
}

function addMessageToChat(message, isUser) {
    const chatMessages = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user-message' : 'ai-message'} ${isUser ? 'user' : 'ai'}`;
    messageDiv.innerHTML = marked.parse(message);
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Handle Enter key in chat input
document.getElementById('chatInput').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        sendMessage();
    }
});
