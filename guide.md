# Opinova User Guide

Welcome to the Opinova Dashboard! This guide will help you navigate the system and start analyzing feedback effectively.

## 1. Getting Started

### Launching the Application
Double-click the shortcut or run `python startapp.py` in your terminal. The Opinova window will appear.

### Logging In
Use the default credentials to access the system:
- **User ID**: `admin`
- **Password**: `admin123`
*(We highly recommend changing these from the Settings menu after your first login).*

## 2. Managing Feedback Files

### Uploading a CSV
1. Click the **Upload CSV** button in the top right corner of the Dashboard.
2. Select a `.csv` file containing feedback data.
3. Once uploaded, the file will appear in the dropdown menu at the top.

### Analyzing a File
1. Select your uploaded file from the top dropdown menu.
2. Click the **Analyze** button.
3. The system will process the feedback, group similar items into clusters, and assign priority scores. **Note**: Analysis may take a few minutes depending on the size of the file.

### Deleting a File
To remove a file and its associated analysis data, select the file from the dropdown and click **Delete**. This will automatically clear the associated cache to prevent conflicts.

## 3. Navigating the Dashboard

- **Dashboard**: View high-level metrics, total feedback processed, and critical issue distributions.
- **Action Items**: View specific feedback clusters that have been marked as needing attention. You can mark them as `solved` or `pending`.
- **Reports**: Generate and export CSV or PDF reports of your analyzed data.
- **Activity Logs**: View system events (e.g., when a file was uploaded or analyzed).
- **Settings**: Change your login credentials, toggle Dark Mode, clear system logs, or configure analysis language whitelists.

## 4. Privacy & Data Handling
All your files and analysis results are strictly stored on your local machine in the `data/` folder. For more details, refer to the Privacy Policy linked at the bottom of the sidebar.
