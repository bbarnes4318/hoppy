"""
Integration script to connect fefast4.py output to Hopwhistle API
This script reads from fefast4.py output and posts to /api/calls/ingest
"""
import json
import sys
import requests
from datetime import datetime
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("HOPWHISTLE_API_URL", "http://localhost:8000")
API_TOKEN = os.getenv("HOPWHISTLE_API_TOKEN", "")  # Optional: for webhook auth


def parse_fefast4_output(analysis_text: str, transcript: str) -> dict:
    """
    Parse fefast4.py analysis output into structured data.
    This is a simplified parser - adjust based on actual fefast4.py output format.
    """
    import re
    
    # Extract billable status
    billable_match = re.search(r'Billable:\s*(Yes|No)', analysis_text, re.IGNORECASE)
    billable = billable_match.group(1).lower() == 'yes' if billable_match else False
    
    # Extract application submitted (sale_made)
    sale_match = re.search(r'Application Submitted:\s*(Yes|No)', analysis_text, re.IGNORECASE)
    sale_made = sale_match.group(1).lower() == 'yes' if sale_match else False
    
    # Extract sale amount (if available)
    amount_match = re.search(r'Monthly Premium:\s*\$?(\d+)', analysis_text, re.IGNORECASE)
    sale_amount_cents = None
    if amount_match and sale_made:
        sale_amount_cents = int(amount_match.group(1)) * 100  # Convert to cents
    
    # Extract agent name
    agent_match = re.search(r'Agent Name:\s*([^\n]+)', analysis_text, re.IGNORECASE)
    agent_name = agent_match.group(1).strip() if agent_match else None
    
    # Extract sentiment
    sentiment_match = re.search(r'Sentiment:\s*(pos|neu|neg|positive|neutral|negative)', analysis_text, re.IGNORECASE)
    sentiment = None
    if sentiment_match:
        s = sentiment_match.group(1).lower()
        if s.startswith('pos'):
            sentiment = "pos"
        elif s.startswith('neu'):
            sentiment = "neu"
        elif s.startswith('neg'):
            sentiment = "neg"
    
    # Extract key points (simplified)
    key_points = []
    if "Key Points:" in analysis_text or "key points" in analysis_text.lower():
        # Try to extract bullet points
        points_match = re.findall(r'[-•]\s*([^\n]+)', analysis_text)
        key_points = [p.strip() for p in points_match[:5]]  # Limit to 5
    
    return {
        "billable": billable,
        "sale_made": sale_made,
        "sale_amount_cents": sale_amount_cents,
        "agent_name": agent_name,
        "sentiment": sentiment,
        "key_points": key_points if key_points else None,
    }


def ingest_call_to_api(
    external_call_id: str,
    partner_id: Optional[str],
    started_at: datetime,
    ended_at: Optional[datetime],
    duration_sec: Optional[int],
    disposition: str,
    transcript: Optional[str],
    analysis: Optional[str],
    **kwargs
) -> bool:
    """
    Ingest a call to the Hopwhistle API
    """
    # Parse analysis if provided
    parsed = {}
    if analysis:
        parsed = parse_fefast4_output(analysis, transcript or "")
    
    # Build payload
    payload = {
        "external_call_id": external_call_id,
        "partner_id": partner_id,
        "started_at": started_at.isoformat() + "Z",
        "disposition": disposition,
        "billable": parsed.get("billable", False),
        "sale_made": parsed.get("sale_made", False),
        **kwargs,
    }
    
    if ended_at:
        payload["ended_at"] = ended_at.isoformat() + "Z"
    if duration_sec:
        payload["duration_sec"] = duration_sec
    if parsed.get("sale_amount_cents"):
        payload["sale_amount_cents"] = parsed["sale_amount_cents"]
    if parsed.get("agent_name"):
        payload["agent_name"] = parsed["agent_name"]
    
    # Add transcript
    if transcript:
        payload["transcript"] = {
            "language": "en",
            "text": transcript,
        }
    
    # Add summary
    if analysis:
        summary_text = analysis[:500]  # Truncate if too long
        payload["summary"] = {
            "summary": summary_text,
            "key_points": parsed.get("key_points"),
            "sentiment": parsed.get("sentiment"),
        }
    
    # Post to API
    headers = {"Content-Type": "application/json"}
    if API_TOKEN:
        headers["Authorization"] = f"Bearer {API_TOKEN}"
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/calls/ingest",
            json=payload,
            headers=headers,
            timeout=10,
        )
        response.raise_for_status()
        print(f"✅ Ingested call {external_call_id}")
        return True
    except Exception as e:
        print(f"❌ Failed to ingest call {external_call_id}: {e}")
        return False


def main():
    """
    Main function - can be called from fefast4.py or run standalone
    Example usage from fefast4.py:
    
    from scripts.integrate_fefast4 import ingest_call_to_api
    
    # After processing a call:
    ingest_call_to_api(
        external_call_id=url_hash,
        partner_id="publisher-co",  # or UUID
        started_at=datetime.utcnow(),
        ended_at=datetime.utcnow(),
        duration_sec=131,
        disposition="connected",
        transcript=transcript,
        analysis=analysis,
        ani="+18665551212",
        dnis="+18665550000",
    )
    """
    print("Hopwhistle API Integration Script")
    print(f"API URL: {API_BASE_URL}")
    print("\nThis script can be imported into fefast4.py or run standalone.")
    print("See the main() function for usage examples.")


if __name__ == "__main__":
    main()

