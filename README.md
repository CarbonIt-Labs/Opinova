# Opinova
## AI-Powered Decision Intelligence Platform

**Turning collective opinions into intelligent decisions.**

Developed by **CarbonIt Labs**  
Created by **Edwin Sam K Reju**

---

Opinova is an AI-powered decision intelligence platform that transforms thousands of opinions, complaints, and suggestions into clear priorities and actionable insights.

Organizations receive large amounts of feedback every day, but the real challenge is:

> *"What matters most, and what should be done first?"*

Opinova helps institutions understand collective voices, identify critical concerns, and convert feedback into meaningful actions using local-first intelligence.

---

# 🌟 Vision

Opinova aims to build a smarter bridge between human voices and institutional decisions.

Every opinion contains a signal. Opinova helps discover:
- **What people are saying** (Feedback clustering & pattern recognition)
- **Why it matters** (Impact, criticality, and urgency evaluation)
- **What actions should be considered** (Actionable recommendations & explainable insights)

---

# ⚡ Key Capabilities

## 🧠 Intelligent Feedback Understanding
Analyzes textual feedback beyond simple keyword counting by identifying deep semantic patterns, concerns, and recurring themes.

## 🎯 Priority-Based Decision Support
Evaluates civic and organizational issues using a multi-factor priority engine:
- **Criticality & Urgency**
- **Impact & Volume of People Affected**
- **Overall Importance Scoring**

Helping organizations focus resources on what matters most.

## 🔍 Explainable Insights
Provides clear, human-understandable reasoning behind its automated analysis:
- Rationale for issue prioritization
- Key quotes and feedback indices
- Specific, recommended next steps

## 📊 Decision Intelligence Dashboard
An intuitive, responsive interface providing:
- Real-time issue distribution & category charts
- Action Item management (Pending/Solved status tracking)
- Flexible CSV / PDF report export capabilities
- Activity logs and offline database management

---

# 🏫 Use Cases


## Organizations & Municipalities
- Employee and citizen feedback intelligence
- Public service complaint resolution (Water, Drainage, Transport, Lighting)
- Supporting data-driven administrative decisions

## Educational Institutions
- Student feedback analysis
- Campus infrastructure improvement
- Identifying urgent academic & facility concerns

## Communities
- Understanding public opinion across geographical/ward divisions
- Structuring raw feedback into actionable civic projects

---

# 🛠️ Technical Architecture & Requirements

Opinova is designed as a **local-first desktop application** prioritizing data privacy and fast offline capabilities.

### Dependencies & Requirements
All project requirements are specified in `requirements.txt`:
- **`pywebview`**: Native desktop UI container
- **`pandas`**: High-performance data manipulation & CSV handling
- **`google-genai`**: Google Generative AI integration for intelligent summaries
- **`python-dotenv`**: Environment variable management
- **`pydantic`**: Data validation & schema enforcement
- **`scikit-learn`**: Machine learning utilities & vector embeddings
- **`nltk` / `spacy`**: Natural Language Processing pipelines
- **`rapidfuzz`**: Fast fuzzy text deduplication & string matching
- **`langdetect`**: Automatic language identification
- **`reportlab`**: PDF report generation engine

To install all requirements:
```bash
pip install -r requirements.txt
```

### Complete Repository Structure
```
OPINOVA/
├── backend/
│   ├── main.py            # API controller, PyWebView window initialization & event routing
│   ├── database.py        # SQLite schema, query helpers, and feedback cache management
│   ├── ai_engine.py       # LLM generation and decision intelligence pipeline
│   ├── preprocessing.py   # Text cleaning, normalization, and token filtering
│   ├── clustering.py      # Feedback grouping and semantic cluster creation
│   ├── scoring.py         # Priority scoring based on urgency, impact, and criticality
│   ├── deduplication.py   # Rapid fuzzy text matching and duplicate removal
│   ├── reports.py         # Automated PDF and CSV report builder
│   ├── batching.py        # Efficient batch processing for large feedback datasets
│   ├── data_loader.py     # CSV parsing and data ingestion module
│   └── config.py          # Backend configuration constants and settings
├── frontend/
│   ├── index.html         # Main interactive dashboard view
│   ├── signinlogin.html   # Login interface
│   ├── privacy.html       # Privacy Policy disclosure
│   └── terms.html         # Acceptable Use Policy disclosure
├── data/                  # Auto-created directory for SQLite database & uploaded datasets
├── .env                   # Configuration
├── startapp.py            # Main application launcher
├── logo.png               # Main branding logo
├── logo.ico               # Converted Windows icon asset
├── LICENSE                # Apache License 2.0 file
├── requirements.txt       # Project dependencies
├── README.md              # Technical overview & platform documentation
└── guide.md               # User manual and deployment guide
```

---

# 🚀 Getting Started

### Quick Start
1. Clone or download the repository to your local machine.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application launcher:
   ```bash
   python startapp.py
   ```

### Default Credentials
On initial startup, default administrator credentials are automatically initialized:
- **User ID**: `admin`
- **Password**: `admin123`

*(Credentials can be updated anytime inside the Dashboard's **Settings** panel.)*

---

# 🔮 Future Roadmap

- Real-time feedback streaming & live intelligence
- Enterprise-grade cloud deployment option
- Multi-language advanced sentiment & dialect analysis
- Custom institutional integrations & API webhooks
- Predictive decision-support models

---

# 👨‍💻 Creator

**Edwin Sam K Reju**  
Founder / Developer at **CarbonIt Labs**

---

# 📜 License

This project is licensed under the **Apache License 2.0**.

The Apache License 2.0 allows:
- Commercial use
- Modification
- Distribution
- Private use

while providing attribution requirements and contributor protections. See the `LICENSE` file for full terms.

---

© 2026 Edwin Sam K Reju
**Millions of opinions.  
One intelligent direction.**
