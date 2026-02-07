"""
Test Twilio call to verify setup
"""
import os
from dotenv import load_dotenv
from twilio.rest import Client

# Load environment variables
load_dotenv()

def make_test_call():
    # Get Twilio credentials
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    from_number = os.getenv('TWILIO_PHONE_NUMBER', '').strip()
    to_number = '+447585488025'
    
    if not account_sid or not auth_token or not from_number:
        print("❌ Missing Twilio credentials in .env file")
        print(f"   TWILIO_ACCOUNT_SID: {'✓' if account_sid else '✗'}")
        print(f"   TWILIO_AUTH_TOKEN: {'✓' if auth_token else '✗'}")
        print(f"   TWILIO_PHONE_NUMBER: {'✓' if from_number else '✗'}")
        return
    
    print(f"📞 Making test call...")
    print(f"   From: {from_number}")
    print(f"   To: {to_number}")
    
    try:
        # Initialize Twilio client
        client = Client(account_sid, auth_token)
        
        # Make the call
        call = client.calls.create(
            to=to_number,
            from_=from_number,
            twiml='<Response><Say voice="Polly.Amy">Hello! This is a test call from SOTA AI Agent Marketplace. If you can hear this message, your Twilio integration is working perfectly. Thank you!</Say></Response>'
        )
        
        print(f"✅ Call initiated successfully!")
        print(f"   Call SID: {call.sid}")
        print(f"   Status: {call.status}")
        print(f"   Direction: {call.direction}")
        print(f"\n💡 Check status at: https://console.twilio.com/us1/monitor/logs/calls/{call.sid}")
        
    except Exception as e:
        print(f"❌ Error making call: {e}")
        if "verify" in str(e).lower():
            print("\n💡 Note: On free trial, you must verify the destination number at:")
            print("   https://console.twilio.com/us1/develop/phone-numbers/manage/verified")

if __name__ == "__main__":
    make_test_call()
