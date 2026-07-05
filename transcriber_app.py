import os
import time
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
import google.generativeai as genai
from pydub import AudioSegment
import streamlit as st

# Load environment variables
load_dotenv()

# ==========================================
# 1. YOUR CORE TRANSCRIPTION BACKEND LOGIC
# ==========================================
class ChunkedAudioTranscriber:
    def __init__(self, chunk_duration_minutes=25, domain="general"):
        self.chunk_duration_minutes = chunk_duration_minutes
        self.chunk_duration_ms = chunk_duration_minutes * 60 * 1000  # Convert to milliseconds
        self.domain = domain
        
        google_key = os.getenv('GOOGLE_API_KEY')
        if not google_key:
            raise ValueError('GOOGLE_API_KEY not found in environment variables or .env file')
        
        genai.configure(api_key=google_key)
        self.model = genai.GenerativeModel("gemini-3.5-flash")
    
    def split_audio(self, audio_file_path: str) -> list:
        audio = AudioSegment.from_file(audio_file_path)
        total_duration_ms = len(audio)
        
        if total_duration_ms <= self.chunk_duration_ms:
            return [(audio_file_path, 0, total_duration_ms)]
        
        chunks = []
        chunk_start = 0
        chunk_number = 1
        temp_dir = tempfile.mkdtemp()
        
        while chunk_start < total_duration_ms:
            chunk_end = min(chunk_start + self.chunk_duration_ms, total_duration_ms)
            chunk_audio = audio[chunk_start:chunk_end]
            
            chunk_filename = os.path.join(temp_dir, f"chunk_{chunk_number:03d}.mp3")
            chunk_audio.export(chunk_filename, format="mp3")
            
            chunks.append((chunk_filename, chunk_start, chunk_end))
            chunk_start = chunk_end
            chunk_number += 1
            
        return chunks
    
    def transcribe_chunk(self, chunk_info: tuple, chunk_index: int, total_chunks: int) -> dict:
        chunk_path, start_ms, end_ms = chunk_info
        try:
            chunk_start_time = time.time()
            audio_file = genai.upload_file(path=chunk_path)
            
            while audio_file.state.name == "PROCESSING":
                time.sleep(3)
                audio_file = genai.get_file(audio_file.name)
            
            if audio_file.state.name == "FAILED":
                return {'success': False, 'error': 'Processing failed', 'transcript': '', 'start_time': start_ms, 'end_time': end_ms}
            
            # Dynamic Context Mapping
            domain_context = {
                "sermon": "a religious/biblical teaching or spoken sermon. Ensure theological terms are spelled accurately.",
                "ngo fieldwork": "an unstructured community field interview or NGO workflow audio. Focus on preserving localized conversational phrasing accurately.",
                "lecture": "an academic lecture or presentation. Maintain technical terms, names, and academic jargon precision.",
                "general": "a continuous spoken audio recording or long-form monologue."
            }
            selected_context = domain_context.get(self.domain.lower(), domain_context["general"])

            prompt = f"""Please transcribe this audio chunk accurately. This is part {chunk_index + 1} of {total_chunks} from {selected_context}

Instructions:
- Provide the complete transcript text for this audio segment
- Include proper punctuation and capitalization
- Organize into paragraphs where natural shifts occur
- If this chunk starts or ends mid-sentence, begin/end naturally
- Do not add any commentary, analysis, or chunk number references
- If there are unclear sections, use [unclear] notation
- IMPORTANT: If there are long pauses (3+ seconds), replace them with two empty lines (double line break)"""
            
            response = self.model.generate_content([prompt, audio_file])
            genai.delete_file(audio_file.name)
            chunk_time = time.time() - chunk_start_time
            
            if response.text:
                transcript = response.text.strip()
                return {
                    'success': True, 'error': None, 'transcript': transcript,
                    'start_time': start_ms, 'end_time': end_ms,
                    'processing_time': chunk_time, 'word_count': len(transcript.split())
                }
            return {'success': False, 'error': 'No text generated', 'transcript': '', 'start_time': start_ms, 'end_time': end_ms}
                
        except Exception as e:
            # THIS LINE WILL FORCE THE TRUE ERROR TO PRINT IN VS CODE
            print(f"❌ INTERNAL ERROR CAUGHT: {str(e)}")
            return {'success': False, 'error': str(e), 'transcript': '', 'start_time': start_ms, 'end_time': end_ms, 'processing_time': 0}
    
    def merge_transcriptions(self, chunk_results: list) -> dict:
        successful_chunks = [r for r in chunk_results if r['success']]
        if not successful_chunks:
            return {'success': False, 'error': 'All chunks failed', 'transcript': ''}
        
        full_transcript_parts = [result['transcript'] for result in successful_chunks]
        total_words = sum(result.get('word_count', 0) for result in successful_chunks)
        
        full_transcript = '\n\n'.join(full_transcript_parts).replace('\n\n\n', '\n\n')
        
        return {
            'success': True, 'error': None, 'transcript': full_transcript,
            'total_chunks': len(chunk_results), 'successful_chunks': len(successful_chunks),
            'total_words': total_words, 'chunk_results': chunk_results
        }

    def transcribe_long_audio(self, audio_file_path: str) -> dict:
        overall_start_time = time.time()
        chunks = self.split_audio(audio_file_path)
        chunk_results = []
        
        # Streamlit progress tracking hooks directly here!
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, chunk_info in enumerate(chunks):
            status_text.text(f"Processing part {i+1} of {len(chunks)}...")
            chunk_result = self.transcribe_chunk(chunk_info, i, len(chunks))
            chunk_results.append(chunk_result)
            progress_bar.progress((i + 1) / len(chunks))
            if i < len(chunks) - 1:
                time.sleep(1)
        
        # Cleanup temp chunks
        for chunk_path, _, _ in chunks:
            if chunk_path != audio_file_path and os.path.exists(chunk_path):
                try:
                    os.remove(chunk_path)
                    os.rmdir(os.path.dirname(chunk_path))
                except:
                    pass
        
        final_result = self.merge_transcriptions(chunk_results)
        final_result['total_processing_time'] = time.time() - overall_start_time
        return final_result

# ==========================================
# 2. STREAMLIT RUNTIME UI INTERFACE
# ==========================================
st.set_page_config(page_title="AI Audio Transcriber", page_icon="🎙️")
st.title("🎙️ Production-Ready Audio Transcriber")
st.write("Bypass API thresholds through automated file chunking processing pipelines.")

uploaded_file = st.file_uploader("Drop runtime audio file here (MP3, WAV, M4A):", type=["mp3", "wav", "m4a"])
target_domain = st.selectbox("Optimized AI Domain Context:", ["General", "Sermon", "NGO Fieldwork", "Lecture"])

if uploaded_file is not None:
    file_size_mb = uploaded_file.size / (1024 * 1024)
    st.info(f"📂 File Target Loaded: {uploaded_file.name} ({file_size_mb:.2f} MB)")
    
    if st.button("🚀 Run Transcription Pipeline", use_container_width=True):
        # Handle the runtime memory stream to path translation
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as temp_file:
            temp_file.write(uploaded_file.read())
            temp_audio_path = temp_file.name

        try:
            transcriber = ChunkedAudioTranscriber(chunk_duration_minutes=25, domain=target_domain)
            result = transcriber.transcribe_long_audio(temp_audio_path)
            
            if result['success']:
                st.success("🎉 Processing Engine Pipeline Finished Safely!")
                
                # Metrics UI Layout
                col1, col2 = st.columns(2)
                col1.metric("Words Transcribed", f"{result['total_words']:,}")
                col2.metric("Processing Time", f"{result['total_processing_time']:.1f}s")
                
                st.subheader("📜 Transcribed Document Output")
                st.text_area("Plain Text Preview", value=result['transcript'], height=350)
                
                st.download_button(
                    label="📥 Save to Local Disk (.txt)",
                    data=result['transcript'],
                    file_name=f"transcript_export.txt",
                    mime="text/plain"
                )
            else:
                st.error(f"Execution Error: {result['error']}")
                
        finally:
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)