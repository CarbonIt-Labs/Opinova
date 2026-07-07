# Opinova  V2 - Project Walkthrough

The platform has been fully upgraded to the **V2 Batch Architecture**. This dramatically reduces API costs and time, while generating deep, defensible AI insights.

## Key Upgrades

1. **Batch AI Analyzer**: 
   - Feedback is now chunked into batches of 50 (configurable in `.env` via `BATCH_SIZE`).
   - Gemini processes entire batches in a single API call, returning fully formed clusters.
2. **Defensible Reasoning**:
   - The AI now generates a `confidence` score, a `reasoning` block, and a `recommended_action` for every single issue.
3. **Smart Retries**:
   - Built-in exponential backoff strictly follows the `5s, 15s, 30s, 60s` retry cascade to safely handle `429` and `503` errors from the API.
4. **Streamlit Dashboard MVP**:
   - Added a beautiful, interactive dashboard to visually explore the generated JSON reports.

## Running the V2 Pipeline

1. **Install new dependencies** (we added Streamlit):
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Batch Analyzer**:
   ```bash
   python main.py analyze data/feedback.csv
   ```
   *You'll notice it processes the entire file in just 1 or 2 API calls!*

3. **Check the CLI Output**:
   ```bash
   python main.py top-issues
   ```
   *You will now see the `WHY THIS MATTERS`, `RECOMMENDED ACTION`, and `AI CONFIDENCE` printed directly in the terminal.*

4. **Launch the Dashboard!**:
   ```bash
   streamlit run streamlit_app.py
   ```
   *This will open a local web page displaying your total metrics, active categories, and a prioritized list of issues with expandable accordions for the AI's reasoning.*
