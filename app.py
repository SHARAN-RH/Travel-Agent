from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import google.generativeai as genai
from dotenv import load_dotenv
import os
import requests

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel('gemini-1.5-flash')

class TravelRequest(BaseModel):
    source: str
    destination: str
    start_date: str
    end_date: str
    budget: float
    num_travelers: int
    interests: List[str]

class ChatRequest(BaseModel):
    question: str
    travel_plan: str
    budget: float
    travelers: int
    interests: list[str]
    include_flights: bool = False

def get_flight_data(source, destination, start_date):
    try:
        print(f"[DEBUG] get_flight_data called with: source={source}, destination={destination}, start_date={start_date}")
        # Validate inputs
        if not all([source, destination, start_date]):
            print("Error: Missing required flight search parameters")
            return None
            
        # Convert airport codes to uppercase
        source_code = source.strip().upper()
        dest_code = destination.strip().upper()
        
        # Validate API key
        serp_api_key = os.getenv("SERP_API_KEY")
        if not serp_api_key:
            print("Error: SERP_API_KEY environment variable not set")
            return None

        print(f"Fetching flight data for {source_code} to {dest_code} on {start_date}")
        
        url = "https://serpapi.com/search.json"
        params = {
            "engine": "google_flights",
            "departure_id": source_code,
            "arrival_id": dest_code,
            "outbound_date": start_date,
            "currency": "USD",
            "hl": "en",
            "type": "2",  # One-way flight
            "api_key": serp_api_key
        }

        print(f"Making request to SerpAPI with params: {params}")
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()  # Raise HTTPError for bad responses
        
        data = response.json()
        
        # Log the response for debugging (be careful with sensitive data in production)
        print(f"[DEBUG] Received flight data: {data}")
        
        if "error" in data:
            print(f"Error from SerpAPI: {data.get('error')}")
            return None
            
        return data
        
    except requests.exceptions.RequestException as e:
        print(f"Request error fetching flight data: {str(e)}")
        return None
    except Exception as e:
        print(f"Unexpected error in get_flight_data: {str(e)}")
        return None

def format_flight_details_markdown(flight_data, source_code, dest_code, start_date):
    if not flight_data or "best_flights" not in flight_data:
        return "No flights available for this route."

    markdown = "## Available Flight Options\n\n"
    markdown += "| Airline | Flight(s) | Departure | Arrival | Duration | Price | Features |\n"
    markdown += "|---------|-----------|-----------|----------|----------|--------|----------|\n"

    for option in flight_data["best_flights"][:3]:  # Limit to 3 flights
        # Get first and last flight for departure and arrival times
        first_flight = option["flights"][0]
        last_flight = option["flights"][-1]

        # Format flight numbers
        flight_numbers = " + ".join([f"{flight['airline']} {flight['flight_number']}" for flight in option["flights"]])

        # Get departure and arrival details
        departure = f"{first_flight['departure_airport']['name']} ({first_flight['departure_airport']['time']})"
        arrival = f"{last_flight['arrival_airport']['name']} ({last_flight['arrival_airport']['time']})"

        # Calculate total duration in hours and minutes
        total_duration = f"{option['total_duration'] // 60}h {option['total_duration'] % 60}m"

        # Get unique features
        features = set()
        for flight in option["flights"]:
            features.update([ext for ext in flight.get("extensions", []) if "Carbon emissions" not in ext])
        features_str = "<br>".join(list(features)[:3])  # Show top 3 features
        
        booking_link = f"[Book Now](https://www.google.com/flights?hl=en#flt={source_code}.{dest_code}.{start_date})"
        markdown += f"| {first_flight['airline']} | {flight_numbers} | {departure} | {arrival} | {total_duration} | ${option['price']} | {features_str} |\n"
        markdown += f"*{booking_link}*\n\n"

        if "layovers" in option:
            markdown += f"*Layover at: {option['layovers'][0]['name']} ({option['layovers'][0]['duration'] // 60}h {option['layovers'][0]['duration'] % 60}m)*\n\n"

    return markdown

@app.post("/plan-trip")
async def generate_travel_plan(request: TravelRequest):
    print("\n=== New Travel Plan Request ===")
    print(f"Source: {request.source}")
    print(f"Destination: {request.destination}")
    print(f"Dates: {request.start_date} to {request.end_date}")
    print(f"Budget: ${request.budget}")
    print(f"Travelers: {request.num_travelers}")
    print(f"Interests: {request.interests}")
    print(f"Include Flights: {getattr(request, 'include_flights', False)}")
    
    try:
        # Construct the prompt
        prompt = f"""
        Create a detailed travel plan with the following details:
        From: {request.source}
        To: {request.destination}
        Dates: {request.start_date} to {request.end_date}
        Budget: ${request.budget}
        Number of Travelers: {request.num_travelers}
        Interests: {', '.join(request.interests) if request.interests else 'Not specified'}

        Please provide:
        1. Day-by-day itinerary
        2. Estimated costs breakdown
        3. Recommended accommodations
        4. Must-visit places based on the interests
        5. Local transportation options
        6. Food recommendations
        7. Tips and precautions
        """

        # Get flight details if requested
        flight_data = None
        if getattr(request, 'include_flights', False):
            print("\n=== Fetching Flight Data ===")
            try:
                print(f"Requesting flight data for {request.source} to {request.destination} on {request.start_date}")
                flight_data = get_flight_data(
                    request.source, 
                    request.destination,
                    request.start_date
                )
                
                if flight_data:
                    print("Successfully retrieved flight data")
                    print(f"Flight data type: {type(flight_data)}")
                    print(f"Flight data keys: {flight_data.keys() if hasattr(flight_data, 'keys') else 'N/A'}")
                    
                    flight_context = """
                    First, analyze these flight options (showing top 3 best flights) for the journey:
                    {flight_data}

                    Please analyze these flights and create a markdown table showing the best options, including:
                    - Airline and flight numbers
                    - Departure and arrival times
                    - Total duration
                    - Price
                    - Key features (like legroom, Wi-Fi, etc.)
                    - Layover information if any

                    After the flight analysis, please provide a comprehensive travel plan that includes:
                    - A day-by-day itinerary
                    - All the other requested information (costs, accommodations, places to visit, etc.)
                    
                    Make sure to separate the flight analysis and travel plan with clear headings.
                    """.format(flight_data=str(flight_data)[:1000])  # Limit length for logging
                    prompt += flight_context
                else:
                    print("Warning: No flight data returned from API")
                    prompt += "\n\nNote: Could not retrieve flight information. The travel plan will continue without flight details."
                    
            except Exception as e:
                print(f"Error processing flight data: {str(e)}")
                import traceback
                traceback.print_exc()
                prompt += "\n\nNote: An error occurred while retrieving flight information. The travel plan will continue without flight details."

        # Generate response using Gemini
        print("\n=== Generating Travel Plan with Gemini ===")
        print(f"Prompt length: {len(prompt)} characters")
        
        try:
            response = model.generate_content(prompt)
            travel_plan = response.text
            print("Successfully generated travel plan")
            
            formatted_flight_data = None
            if flight_data and getattr(request, 'include_flights', False):
                try:
                    print("\n=== Formatting Flight Details ===")
                    formatted_flight_data = format_flight_details_markdown(
                        flight_data,
                        request.source.strip().upper(),
                        request.destination.strip().upper(),
                        request.start_date
                    )
                    print("Successfully formatted flight details")
                except Exception as e:
                    print(f"Error formatting flight data: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    formatted_flight_data = "Note: Could not format flight details. Showing raw data instead."

            print("\n=== Sending Response ===")
            return {
                "success": True,
                "plan": travel_plan,
                "flight_details": formatted_flight_data if getattr(request, 'include_flights', False) else None
            }
            
        except Exception as e:
            print(f"\n=== Error generating travel plan ===")
            print(f"Error: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Return a helpful error message
            error_msg = f"Error generating travel plan: {str(e)}"
            if "API key" in str(e):
                error_msg += "\nPlease check your GEMINI_API_KEY in the .env file."
            
            return {
                "success": False,
                "error": error_msg
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat_with_plan(request: ChatRequest):
    try:
        # Agentic: Detect if question needs real-time flight data
        flight_keywords = ["flight", "airline", "ticket", "fare", "cheapest", "price"]
        question_lower = request.question.lower()
        needs_flight_data = any(kw in question_lower for kw in flight_keywords)

        flight_context = ""
        formatted_flight_data = None
        if needs_flight_data:
            # Use explicit fields from chat request
            print(f"[DEBUG] /chat: Attempting to fetch flight data for: {getattr(request, 'source', None)}, {getattr(request, 'destination', None)}, {getattr(request, 'start_date', None)}")
            flight_data = get_flight_data(
                getattr(request, 'source', None),
                getattr(request, 'destination', None),
                getattr(request, 'start_date', None)
            )
            print(f"[DEBUG] /chat: flight_data received: {flight_data}")
            if flight_data:
                try:
                    formatted_flight_data = format_flight_details_markdown(
                        flight_data,
                        getattr(request, 'source', ''),
                        getattr(request, 'destination', ''),
                        getattr(request, 'start_date', '')
                    )
                    print(f"[DEBUG] /chat: formatted_flight_data: {formatted_flight_data}")
                    flight_context = f"\n\n### Real-Time Flight Data (via SerpAPI)\n{formatted_flight_data}"
                except Exception as e:
                    print(f"[DEBUG] /chat: Error formatting flight data: {str(e)}")
                    formatted_flight_data = None
                    flight_context = "\n\nNote: Could not format real-time flight information."
            else:
                print("[DEBUG] /chat: No flight data returned from get_flight_data.")
                flight_context = "\n\nNote: Could not retrieve real-time flight information."

        # Blend everything into the Gemini prompt
        prompt = f"""
        Given this travel plan:
        {request.travel_plan}
        {flight_context}

        Please answer this question about the plan (and, if available, use the real-time flight data above):
        {request.question}

        Provide a clear and concise response, using markdown formatting where appropriate.
        If the question is about something not covered in the plan, suggest relevant information or alternatives.
        """
        print(f"[DEBUG] /chat: Gemini prompt being sent:\n{prompt}\n---END PROMPT---")
        response = model.generate_content(prompt)
        return {
            "success": True,
            "response": response.text,
            "flight_details": formatted_flight_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Mount the static files directory
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return FileResponse('static/index.html')
