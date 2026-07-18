import streamlit as st
import json
import os
import pandas as pd

st.set_page_config(page_title="Opinova Dashboard", layout="wide")

st.title("Opinova - Decision Intelligence Dashboard")
st.markdown("Automated AI feedback clustering and prioritization.")

PROCESSED_FILE = "data/processed_results.json"

if not os.path.exists(PROCESSED_FILE):
    st.warning("No data found. Please run the CLI tool first: `python main.py analyze data/feedback.csv`")
else:
    with open(PROCESSED_FILE, "r") as f:
        clusters = json.load(f)
        
    if not clusters:
        st.info("No clusters to display.")
    else:
        # Metrics Row
        total_feedback = sum([c['frequency'] for c in clusters])
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Feedback Items", total_feedback)
        col2.metric("Identified Clusters", len(clusters))
        immediate_count = len([c for c in clusters if c['category'] == "Immediate Action Required"])
        col3.metric("Immediate Actions Required", immediate_count)
        
        st.divider()
        
        # Display Top Issues
        st.subheader("Top Prioritized Issues")
        
        sorted_clusters = sorted(clusters, key=lambda x: x['priority_score'], reverse=True)
        
        for c in sorted_clusters:
            with st.expander(f"[{c['priority_score']}/100] {c['topic']} - {c['category']}"):
                st.markdown(f"**Issue Type:** {c.get('issue_type', 'N/A')}")
                st.markdown(f"**Frequency:** {c['frequency']} items  |  **Users Affected:** ~{c['users_affected_estimate']}")
                
                st.markdown("### Why this matters")
                st.write(c.get('reasoning', 'No reasoning provided.'))
                
                st.markdown("### Recommended Action")
                st.success(c.get('recommended_action', 'Review manually.'))
                
                st.markdown(f"**AI Confidence:** {c.get('confidence', 0)*100:.0f}%")
                
                # Show scores
                st.markdown("**Underlying Scores (out of 10):**")
                s_col1, s_col2, s_col3 = st.columns(3)
                s_col1.metric("Criticality", f"{c['criticality']:.1f}")
                s_col2.metric("Urgency", f"{c['urgency']:.1f}")
                s_col3.metric("Impact", f"{c['impact']:.1f}")
