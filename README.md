#  Production-Ready AI Audio Transcriber

An automated audio transcription pipeline built with **Streamlit** and **Gemini 3.5 Flash**. This application bypasses standard LLM file/token payload thresholds by automatically chunking long audio files into optimal 25-minute segments, processing them via the Google GenAI API, and merging them safely back together.

---

##  Architecture & Data Flow

This application is built to handle long-form audio without running into API payload limits or hitting memory ceilings. 

1. File Upload: The Streamlit UI accepts `MP3`, `WAV`, or `M4A` files up to the maximum browser payload limit.
2. Segmentation Pipeline: `pydub` analyzes the file length. If it exceeds 25 minutes, it splits the audio into sequential, smaller chunks stored in a secure temporary directory.
3. Asynchronous Processing: Chunks are uploaded sequentially to the Gemini API using the `genai.upload_file` pipeline, tracking the processing state until completion.
4. Context Injection: Prompts are dynamically adjusted based on the selected domain (e.g., academic jargon mapping for *Lectures* vs. localized conversational phrasing for *NGO Fieldwork*).
5. Reconstruction Engine: The individual text responses are compiled, formatted with clean double-line breaks for long pauses (3+ seconds), and unified into a single downloadable document.

---

## Installation & Environment Setup

### 1. System Prerequisites
Because this application processes and converts audio files locally, you must have **FFmpeg** installed on your operating system:
* **macOS:** `brew install ffmpeg`
* **Windows (via Chocolatey):** `choco install ffmpeg`
* **Linux:** `sudo apt install ffmpeg`

### 2. Clone and Install Dependencies
```bash
git clone [https://github.com/YOUR_USERNAME/YOUR_REPOSITORY_NAME.git](https://github.com/YOUR_USERNAME/YOUR_REPOSITORY_NAME.git)
cd YOUR_REPOSITORY_NAME
pip install -r requirements.txt

**3.Environment Configuration (.env)**
The application relies on secure environment variables to communicate safely with the Gemini API.

In the root directory of the project, create a new file named .env:

Bash
# On Windows PowerShell:
New-Item .env
# On Linux/macOS Git Bash:
touch .env
Open the .env file in your text editor and add your Google Gemini API key using the exact key name below:

Code snippet
GOOGLE_API_KEY=your_actual_api_key_here

**4. Launching the App**
Once your system paths and environment variables are configured, start the local Streamlit runtime server:

Bash
streamlit run transcriber_app.py
