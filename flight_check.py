import os
import time
import requests
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

load_dotenv()
##############################
#USE FOR LOCAL TESTING
#API_KEY = os.getenv("RAPIDAPI_KEY")
#EMAIL_SENDER = os.getenv("EMAIL_SENDER")
#EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
#EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
##############################


API_KEY = os.getenv("RAPIDAPI_KEY")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")

TARGET_PRICE = 600  # CAD max price threshold
FROM_ENTITY = "YYZ"
TO_ENTITY = "FCO"
DEPART_DATE = "2025-09-12"
AIRLINE_ID = "32695"  # Air Canada

# Allowed departure times to filter on
ALLOWED_DEPARTURES = {"2025-09-12T19:35:00", "2025-09-12T21:20:00"}

HEADERS = {
    "x-rapidapi-key": API_KEY,
    "x-rapidapi-host": "flights-sky.p.rapidapi.com"
}

def send_email(price, flight):
    legs = flight.get("legs", [])
    leg_details = []
    for i, leg in enumerate(legs, start=1):
        origin = leg["origin"]["city"]
        origin_code = leg["origin"]["displayCode"]
        dest = leg["destination"]["city"]
        dest_code = leg["destination"]["displayCode"]
        depart = leg["departure"].replace("T", " ")
        arrive = leg["arrival"].replace("T", " ")
        duration = leg.get("durationInMinutes", 0)
        stops = leg.get("stopCount", 0)
        carriers = ", ".join(c["name"] for c in leg["carriers"]["marketing"])

        leg_details.append(
            f"Leg {i}:\n"
            f"  From: {origin} ({origin_code})\n"
            f"  To: {dest} ({dest_code})\n"
            f"  Departure: {depart}\n"
            f"  Arrival: {arrive}\n"
            f"  Duration: {duration} minutes\n"
            f"  Stops: {stops}\n"
            f"  Airline(s): {carriers}\n"
        )

    body = f"""\
🎉 Flight Price Alert!

Price dropped to: CAD ${price:.2f}

Flight ID: {flight.get("id")}

{chr(10).join(leg_details)}

Safe travels! ✈️
"""

    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = "✈️ Flight Price Alert!"
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECEIVER

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_SENDER, EMAIL_PASSWORD)
        smtp.send_message(msg)

    print("✅ Email sent!")

def search_flights():
    search_url = "https://flights-sky.p.rapidapi.com/flights/search-one-way"
    params = {
        "fromEntityId": FROM_ENTITY,
        "toEntityId": TO_ENTITY,
        "departDate": DEPART_DATE,
        "currency": "CAD",
        "stops": "direct",
        "adults": 1,
        "airlines": AIRLINE_ID
    }
    response = requests.get(search_url, headers=HEADERS, params=params)
    data = response.json()
    if not data.get("status", False):
        print("API error:", data.get("message"))
        return None

    session_id = data["data"]["context"]["sessionId"]
    return session_id

def poll_until_complete(session_id):
    incomplete_url = "https://flights-sky.p.rapidapi.com/flights/search-incomplete"
    while True:
        params = {"sessionId": session_id}
        response = requests.get(incomplete_url, headers=HEADERS, params=params)
        data = response.json()

        status = data["data"]["context"]["status"]
        print(f"Polling status: {status}")

        if status == "complete":
            return data["data"].get("itineraries", [])
        time.sleep(2)

def filter_air_canada_flights(itineraries, max_price=TARGET_PRICE):
    filtered = []
    for flight in itineraries:
        price = flight.get("price", {}).get("raw", float('inf'))
        if price > max_price:
            continue

        legs = flight.get("legs", [])

        # Check all legs' marketing carriers include Air Canada (id = -32695)
        if not all(
            any(carrier.get("id") == -int(AIRLINE_ID) for carrier in leg.get("carriers", {}).get("marketing", []))
            for leg in legs
        ):
            continue

        # Check if any leg departure time matches allowed departure times
        if not any(leg.get("departure") in ALLOWED_DEPARTURES for leg in legs):
            continue

        filtered.append(flight)
    return filtered

def main():
    print("🔎 Searching flights...")
    session_id = search_flights()
    if not session_id:
        print("Failed to get session ID")
        return

    itineraries = poll_until_complete(session_id)
    if not itineraries:
        print("No itineraries found.")
        return

    filtered_flights = filter_air_canada_flights(itineraries, TARGET_PRICE)
    if not filtered_flights:
        print(f"No Air Canada direct flights under CAD ${TARGET_PRICE} found with the specified departure times.")
        return

    for flight in filtered_flights:
        price = flight.get("price", {}).get("raw", 0)
        print(f"Sending alert for flight {flight.get('id')} at price CAD ${price:.2f}")
        send_email(price, flight)

if __name__ == "__main__":
    main()
