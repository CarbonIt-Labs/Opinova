from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from config import GEMINI_API_KEY
import json

class IssueCluster(BaseModel):
    topic: str = Field(description="A short 1-3 word key topic representing the cluster (e.g., 'Cyberbullying', 'Transport Delays')")
    issue_type: str = Field(description="E.g., Complaint, Suggestion, Request, Safety Concern")
    criticality: int = Field(description="Score from 1-10 on how critical the issue is")
    urgency: int = Field(description="Score from 1-10 on how quickly it needs to be addressed")
    impact: int = Field(description="Score from 1-10 on the potential impact of fixing/ignoring it")
    users_affected_estimate: int = Field(description="Estimated number of users affected (e.g. 1, 10, 100) based on context")
    confidence: float = Field(description="AI confidence score between 0.0 and 1.0 on its analysis")
    reasoning: str = Field(description="Explanation of why these scores were given, making the priority defensible")
    recommended_action: str = Field(description="Actionable recommendation on what to do next")
    feedback_indices: list[int] = Field(description="Indices (starting from 0) of the original feedback items in the provided batch that belong to this cluster")

class BatchAnalysisResult(BaseModel):
    clusters: list[IssueCluster]

def analyze_feedback_batch(feedback_list: list[str]) -> BatchAnalysisResult:
    """Analyzes a batch of feedback items in one LLM call and returns grouped clusters."""
    try:
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set. Please set it in your .env file.")
        
        client = genai.Client(api_key=GEMINI_API_KEY)
    
        # Format the input as a numbered list
        formatted_input = ""
        for i, text in enumerate(feedback_list):
            formatted_input += f"[{i}] {text}\n"
        
        prompt = f"""You are an advanced Decision Intelligence AI.
Analyze the following batch of feedback comments. Group them into meaningful clusters based on their core topic.
For each cluster, calculate the severity scores, provide your reasoning, a recommended action, and list the exact indices of the feedback items that belong to it.

Feedback Batch:
{formatted_input}
"""
    
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=BatchAnalysisResult,
                temperature=0.1,
            ),
        )
        return BatchAnalysisResult.model_validate_json(response.text)

    except Exception as e:
        print(f"Exception in ai_engine: {e}")
        raise e
