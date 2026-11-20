"""
Streamlit-based chat interface for Enterprise Document Assistant.
Provides conversational UI for document queries with real-time streaming.
"""

import streamlit as st
import requests
import base64
from io import BytesIO
from typing import List, Dict, Any, Optional
import time
from PIL import Image
from components.image_viewer import display_zoomable_image, display_image_gallery

# Configuration
API_BASE_URL = st.secrets.get("API_BASE_URL", "http://localhost:8000")
API_TIMEOUT = 30

# Page configuration
st.set_page_config(
    page_title="Enterprise Document Assistant",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .stChatMessage {
        padding: 1rem;
        border-radius: 0.5rem;
    }
    .source-card {
        border: 1px solid #ddd;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 0.5rem 0;
        background-color: #f9f9f9;
    }
    .highlight-image {
        border: 2px solid #4CAF50;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize session state variables."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "token" not in st.session_state:
        st.session_state.token = None
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False


def authenticate(username: str, password: str) -> Optional[str]:
    """Authenticate user and return JWT token."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/auth/login",
            json={"username": username, "password": password},
            timeout=API_TIMEOUT
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token")
        return None
    except Exception as e:
        st.error(f"Authentication failed: {str(e)}")
        return None


def upload_document(file, token: str) -> Dict[str, Any]:
    """Upload a document to the API."""
    try:
        files = {"file": (file.name, file, "application/pdf")}
        headers = {"Authorization": f"Bearer {token}"}
        
        response = requests.post(
            f"{API_BASE_URL}/documents/upload",
            files=files,
            headers=headers,
            timeout=API_TIMEOUT
        )
        
        if response.status_code in (200, 201):
            return {"success": True, "data": response.json()}
        else:
            return {"success": False, "error": response.json().get("detail", "Upload failed")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def query_documents(query: str, token: str) -> Dict[str, Any]:
    """Send query to the API and get response."""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.post(
            f"{API_BASE_URL}/query",
            json={"query": query},
            headers=headers,
            timeout=API_TIMEOUT
        )
        
        if response.status_code == 200:
            return {"success": True, "data": response.json()}
        else:
            return {"success": False, "error": response.json().get("detail", "Query failed")}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_highlighted_page(document_id: str, page_num: int, token: str) -> Optional[bytes]:
    """Retrieve highlighted page image from API."""
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            f"{API_BASE_URL}/documents/{document_id}/page/{page_num}",
            headers=headers,
            timeout=API_TIMEOUT
        )
        
        if response.status_code == 200:
            return response.content
        return None
    except Exception as e:
        st.error(f"Failed to load highlighted page: {str(e)}")
        return None


def display_source_attribution(source: Dict[str, Any], token: str, source_index: int):
    """Display a source attribution with highlighted image."""
    with st.container():
        st.markdown(f"""
        <div class="source-card">
            <strong>📄 {source['document_name']}</strong> - Page {source['page_number']}
            <br>
            <small>Relevance: {source['relevance_score']:.2%}</small>
        </div>
        """, unsafe_allow_html=True)
        
        # Display text excerpt
        with st.expander("View text excerpt", expanded=False):
            st.text(source['text_excerpt'])
        
        # Display highlighted image with zoom and pan
        if source.get('highlighted_image_url'):
            # Extract document_id and page from URL or use provided data
            doc_id = source.get('document_id', 'unknown')
            page_num = source['page_number']
            
            # Create expandable section for highlighted image
            with st.expander("🔍 View highlighted page (click to expand)", expanded=True):
                image_data = get_highlighted_page(doc_id, page_num, token)
                if image_data:
                    caption = f"{source['document_name']} - Page {page_num} with highlights"
                    display_zoomable_image(image_data, caption, f"source_{source_index}")
                else:
                    st.warning("Could not load highlighted page image")


def render_sidebar():
    """Render sidebar with document upload and settings."""
    with st.sidebar:
        st.title("📚 Document Assistant")
        
        # Authentication status
        if st.session_state.authenticated:
            st.success("✅ Authenticated")
            if st.button("Logout"):
                st.session_state.authenticated = False
                st.session_state.token = None
                st.session_state.messages = []
                st.rerun()
        
        st.divider()
        
        # Document upload section
        st.subheader("Upload Documents")
        uploaded_file = st.file_uploader(
            "Choose a PDF file",
            type=["pdf"],
            help="Upload proprietary documents for querying"
        )
        
        if uploaded_file and st.session_state.authenticated:
            if st.button("Upload Document"):
                with st.spinner("Uploading and processing document..."):
                    result = upload_document(uploaded_file, st.session_state.token)
                    
                    if result["success"]:
                        st.success(f"✅ Document uploaded: {result['data'].get('filename', result['data'].get('document_name', 'unknown'))}")
                        st.info(f"Processed {result['data']['chunks_created']} chunks")
                    else:
                        st.error(f"❌ Upload failed: {result['error']}")
        
        st.divider()
        
        # Settings
        st.subheader("Settings")
        if st.button("Clear Chat History"):
            st.session_state.messages = []
            st.rerun()
        
        # System info
        st.divider()
        st.caption("Enterprise Document Assistant v1.0")


def render_chat_interface():
    """Render the main chat interface."""
    st.title("💬 Chat with Your Documents")
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            # Display sources if available
            if message.get("sources"):
                st.subheader("Sources")
                for idx, source in enumerate(message["sources"]):
                    display_source_attribution(source, st.session_state.token, idx)
    
    # Chat input
    if prompt := st.chat_input("Ask a question about your documents..."):
        if not st.session_state.authenticated:
            st.error("Please login first")
            return
        
        # Add user message to chat
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get response from API
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                result = query_documents(prompt, st.session_state.token)
                
                if result["success"]:
                    data = result["data"]
                    answer = data["answer"]
                    sources = data.get("sources", [])
                    
                    # Display answer
                    st.markdown(answer)
                    
                    # Display sources
                    if sources:
                        st.subheader("Sources")
                        for idx, source in enumerate(sources):
                            display_source_attribution(source, st.session_state.token, idx)
                    
                    # Add assistant message to chat
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer,
                        "sources": sources
                    })
                else:
                    error_msg = f"❌ Error: {result['error']}"
                    st.error(error_msg)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_msg
                    })


def render_login_page():
    """Render login page."""
    st.title("🔐 Login")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.subheader("Enterprise Document Assistant")
        
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                if username and password:
                    with st.spinner("Authenticating..."):
                        token = authenticate(username, password)
                        
                        if token:
                            st.session_state.token = token
                            st.session_state.authenticated = True
                            st.success("✅ Login successful!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("❌ Invalid credentials")
                else:
                    st.warning("Please enter both username and password")


def main():
    """Main application entry point."""
    initialize_session_state()
    
    if not st.session_state.authenticated:
        render_login_page()
    else:
        render_sidebar()
        render_chat_interface()


if __name__ == "__main__":
    main()
