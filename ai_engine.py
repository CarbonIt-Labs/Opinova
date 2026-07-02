from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from config import GEMINI_API_KEY
import json

class FeedbackAnalysis(BaseModel):
    sentiment: str = Field(description="Positive, Negative, or Neutral")
    topic: str = Field(description="A short 1-3 word key topic extracted from the text. Keep it generic like 'Bullying Reports', 'Transport Delays', 'Website Bugs'")
    is_complaint: bool
    is_suggestion: bool
    criticality: int = Field(description="Score from 1-10 on how critical the issue is")
    urgency: int = Field(description="Score from 1-10 on how quickly it needs to be addressed")
    impact: int = Field(description="Score from 1-10 on the potential impact of fixing/ignoring it")
    users_affected_estimate: int = Field(description="Estimated number of users affected (e.g. 1, 10, 100) based on context")

def analyze_feedback(text: str) -> FeedbackAnalysis:
    """Analyzes a single piece of feedback using Gemini."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set. Please set it in your .env file.")
        
    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"Analyze the following feedback and extract the requested fields:\n\n{text}"
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=FeedbackAnalysis,
            temperature=0.1,
        ),
    )
    return FeedbackAnalysis.model_validate_json(response.text)

def generate_cluster_summary(topic: str, feedback_list: list) -> str:
    """Generates a summary for a cluster of feedback."""
    client = genai.Client(api_key=GEMINI_API_KEY)
    text_list = "\n".join([f"- {f}" for f in feedback_list])
    prompt = f"Summarize the following feedback comments about '{topic}' into a single, concise paragraph:\n{text_list}"
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    return response.text
