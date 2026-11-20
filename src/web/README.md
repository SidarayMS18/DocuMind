# Enterprise Document Assistant - Web Interface

A Streamlit-based chat interface for querying proprietary documents with visual source attribution.

## Features

### Chat Interface (Task 10.1)
- **Conversational UI**: Natural language interface for document queries
- **Real-time Streaming**: Immediate response display as queries are processed
- **File Upload**: Drag-and-drop interface for uploading PDF documents
- **Session Management**: Maintains conversation history during the session
- **Authentication**: Secure JWT-based login system

### Highlighted Image Display (Task 10.2)
- **Visual Source Attribution**: Displays original PDF pages with highlighted text
- **Zoom Functionality**: Zoom in/out with mouse wheel or control buttons (50% - 500%)
- **Pan Capability**: Click and drag to navigate zoomed images
- **Click-to-Expand**: Expandable sections for each source citation
- **Fullscreen Mode**: View highlighted pages in fullscreen for detailed inspection
- **Context Viewing**: View full text context around highlighted sections

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure the API endpoint in `.streamlit/secrets.toml`:
```toml
API_BASE_URL = "http://localhost:8000"
```

## Running the Web Interface

### Option 1: Using the startup script
```bash
python scripts/start_web.py
```

### Option 2: Direct Streamlit command
```bash
streamlit run src/web/app.py
```

The interface will be available at: http://localhost:8501

## Usage

### 1. Login
- Enter your username and password
- Click "Login" to authenticate

### 2. Upload Documents
- Use the sidebar file uploader
- Select a PDF file
- Click "Upload Document"
- Wait for processing confirmation

### 3. Query Documents
- Type your question in the chat input
- Press Enter to submit
- View the AI-generated response with source citations

### 4. Interact with Highlighted Images
- **Zoom**: Use +/- buttons or mouse wheel
- **Pan**: Click and drag the image
- **Reset**: Click "Reset" to return to original view
- **Fullscreen**: Click the fullscreen button for detailed viewing
- **Expand Context**: Click expanders to view full text context

## Components

### Main Application (`app.py`)
- Authentication and session management
- Chat interface rendering
- API communication
- Document upload handling

### Image Viewer (`components/image_viewer.py`)
- Zoomable and pannable image display
- Interactive controls (zoom, pan, reset, fullscreen)
- Mouse wheel zoom support
- Double-click to zoom

### Context Viewer (`components/context_viewer.py`)
- Expandable context sections
- Source navigation
- Side-by-side source comparison
- Full text context display

## Configuration

### Streamlit Configuration (`.streamlit/config.toml`)
- Theme customization
- Server settings
- Browser preferences

### Secrets Configuration (`.streamlit/secrets.toml`)
- API endpoint URL
- Authentication credentials (if needed)

## Requirements Validation

### Requirement 6.1: User-Friendly Chat Interface
✅ Conversational interface similar to popular chat applications
✅ Session-based conversation history
✅ User-friendly error messages

### Requirement 6.2: Response Display with Citations
✅ Responses displayed with embedded highlighted page images
✅ Visual highlighting of source text on original pages
✅ Click-to-expand functionality for detailed viewing

### Requirement 6.6: Interactive Highlighted Text
✅ Zoom and pan functionality for detailed viewing
✅ Context expansion capabilities
✅ Fullscreen mode for detailed inspection

## Troubleshooting

### Connection Issues
- Ensure the FastAPI backend is running on the configured port
- Check `API_BASE_URL` in `.streamlit/secrets.toml`

### Authentication Failures
- Verify credentials with the backend administrator
- Check that the `/auth/login` endpoint is accessible

### Image Display Issues
- Ensure the backend is returning valid image data
- Check browser console for JavaScript errors
- Verify the `/documents/{id}/page/{page_num}` endpoint is working

## Development

### Adding New Features
1. Create new components in `src/web/components/`
2. Import and integrate in `app.py`
3. Update this README with new functionality

### Styling
- Modify CSS in `app.py` for custom styling
- Update theme in `.streamlit/config.toml`

## Security Notes

- All API requests include JWT authentication tokens
- Passwords are never stored in the frontend
- Session state is cleared on logout
- XSRF protection is enabled by default
