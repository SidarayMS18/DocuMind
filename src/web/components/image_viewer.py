"""
Enhanced image viewer component with zoom and pan functionality.
"""

import streamlit as st
import streamlit.components.v1 as components
from typing import Optional
import base64


def create_zoomable_image_html(image_base64: str, caption: str, image_id: str) -> str:
    """
    Create HTML for a zoomable and pannable image viewer.
    
    Args:
        image_base64: Base64 encoded image data
        caption: Image caption
        image_id: Unique identifier for the image
        
    Returns:
        HTML string with interactive image viewer
    """
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            .image-container {{
                position: relative;
                width: 100%;
                max-width: 800px;
                margin: 10px auto;
                border: 2px solid #4CAF50;
                border-radius: 8px;
                overflow: hidden;
                background-color: #f5f5f5;
            }}
            
            .image-wrapper {{
                position: relative;
                width: 100%;
                height: 600px;
                overflow: auto;
                cursor: grab;
            }}
            
            .image-wrapper:active {{
                cursor: grabbing;
            }}
            
            .zoomable-image {{
                display: block;
                max-width: none;
                transition: transform 0.2s ease;
                user-select: none;
            }}
            
            .image-controls {{
                position: absolute;
                top: 10px;
                right: 10px;
                z-index: 10;
                background: rgba(255, 255, 255, 0.9);
                padding: 8px;
                border-radius: 4px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            }}
            
            .control-btn {{
                background: #4CAF50;
                color: white;
                border: none;
                padding: 8px 12px;
                margin: 2px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
                font-weight: bold;
            }}
            
            .control-btn:hover {{
                background: #45a049;
            }}
            
            .control-btn:active {{
                background: #3d8b40;
            }}
            
            .zoom-level {{
                display: inline-block;
                padding: 8px 12px;
                margin: 2px;
                font-size: 14px;
                font-weight: bold;
                color: #333;
            }}
            
            .image-caption {{
                padding: 10px;
                background: #fff;
                text-align: center;
                font-weight: bold;
                color: #333;
                border-top: 1px solid #ddd;
            }}
            
            .fullscreen-btn {{
                position: absolute;
                bottom: 10px;
                right: 10px;
                background: rgba(76, 175, 80, 0.9);
                color: white;
                border: none;
                padding: 10px 15px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
                z-index: 10;
            }}
            
            .fullscreen-btn:hover {{
                background: rgba(69, 160, 73, 0.9);
            }}
        </style>
    </head>
    <body>
        <div class="image-container" id="container-{image_id}">
            <div class="image-controls">
                <button class="control-btn" onclick="zoomIn_{image_id}()">+</button>
                <span class="zoom-level" id="zoom-{image_id}">100%</span>
                <button class="control-btn" onclick="zoomOut_{image_id}()">-</button>
                <button class="control-btn" onclick="resetZoom_{image_id}()">Reset</button>
            </div>
            
            <div class="image-wrapper" id="wrapper-{image_id}">
                <img 
                    class="zoomable-image" 
                    id="image-{image_id}"
                    src="data:image/png;base64,{image_base64}"
                    alt="{caption}"
                />
            </div>
            
            <button class="fullscreen-btn" onclick="toggleFullscreen_{image_id}()">
                ⛶ Fullscreen
            </button>
            
            <div class="image-caption">{caption}</div>
        </div>
        
        <script>
            let scale_{image_id} = 1;
            let isPanning_{image_id} = false;
            let startX_{image_id} = 0;
            let startY_{image_id} = 0;
            let scrollLeft_{image_id} = 0;
            let scrollTop_{image_id} = 0;
            
            const image_{image_id} = document.getElementById('image-{image_id}');
            const wrapper_{image_id} = document.getElementById('wrapper-{image_id}');
            const zoomDisplay_{image_id} = document.getElementById('zoom-{image_id}');
            const container_{image_id} = document.getElementById('container-{image_id}');
            
            function updateZoom_{image_id}() {{
                image_{image_id}.style.transform = `scale(${{scale_{image_id}}})`;
                zoomDisplay_{image_id}.textContent = Math.round(scale_{image_id} * 100) + '%';
            }}
            
            function zoomIn_{image_id}() {{
                scale_{image_id} = Math.min(scale_{image_id} + 0.25, 5);
                updateZoom_{image_id}();
            }}
            
            function zoomOut_{image_id}() {{
                scale_{image_id} = Math.max(scale_{image_id} - 0.25, 0.5);
                updateZoom_{image_id}();
            }}
            
            function resetZoom_{image_id}() {{
                scale_{image_id} = 1;
                updateZoom_{image_id}();
                wrapper_{image_id}.scrollLeft = 0;
                wrapper_{image_id}.scrollTop = 0;
            }}
            
            function toggleFullscreen_{image_id}() {{
                if (!document.fullscreenElement) {{
                    container_{image_id}.requestFullscreen().catch(err => {{
                        console.error('Error entering fullscreen:', err);
                    }});
                }} else {{
                    document.exitFullscreen();
                }}
            }}
            
            // Pan functionality
            wrapper_{image_id}.addEventListener('mousedown', (e) => {{
                isPanning_{image_id} = true;
                startX_{image_id} = e.pageX - wrapper_{image_id}.offsetLeft;
                startY_{image_id} = e.pageY - wrapper_{image_id}.offsetTop;
                scrollLeft_{image_id} = wrapper_{image_id}.scrollLeft;
                scrollTop_{image_id} = wrapper_{image_id}.scrollTop;
            }});
            
            wrapper_{image_id}.addEventListener('mouseleave', () => {{
                isPanning_{image_id} = false;
            }});
            
            wrapper_{image_id}.addEventListener('mouseup', () => {{
                isPanning_{image_id} = false;
            }});
            
            wrapper_{image_id}.addEventListener('mousemove', (e) => {{
                if (!isPanning_{image_id}) return;
                e.preventDefault();
                const x = e.pageX - wrapper_{image_id}.offsetLeft;
                const y = e.pageY - wrapper_{image_id}.offsetTop;
                const walkX = (x - startX_{image_id}) * 2;
                const walkY = (y - startY_{image_id}) * 2;
                wrapper_{image_id}.scrollLeft = scrollLeft_{image_id} - walkX;
                wrapper_{image_id}.scrollTop = scrollTop_{image_id} - walkY;
            }});
            
            // Zoom with mouse wheel
            wrapper_{image_id}.addEventListener('wheel', (e) => {{
                e.preventDefault();
                if (e.deltaY < 0) {{
                    zoomIn_{image_id}();
                }} else {{
                    zoomOut_{image_id}();
                }}
            }});
            
            // Double-click to zoom
            image_{image_id}.addEventListener('dblclick', (e) => {{
                if (scale_{image_id} === 1) {{
                    scale_{image_id} = 2;
                }} else {{
                    scale_{image_id} = 1;
                }}
                updateZoom_{image_id}();
            }});
        </script>
    </body>
    </html>
    """
    return html


def display_zoomable_image(image_data: bytes, caption: str, image_id: str):
    """
    Display an image with zoom and pan capabilities.
    
    Args:
        image_data: Raw image bytes
        caption: Image caption
        image_id: Unique identifier for the image
    """
    # Convert image to base64
    image_base64 = base64.b64encode(image_data).decode()
    
    # Create and display the HTML component
    html = create_zoomable_image_html(image_base64, caption, image_id)
    components.html(html, height=700, scrolling=False)


def display_image_gallery(images: list, captions: list):
    """
    Display multiple images in a gallery with zoom capabilities.
    
    Args:
        images: List of image data (bytes)
        captions: List of captions for each image
    """
    if len(images) != len(captions):
        st.error("Number of images and captions must match")
        return
    
    # Create tabs for each image
    if len(images) > 1:
        tabs = st.tabs([f"Source {i+1}" for i in range(len(images))])
        for i, (tab, image_data, caption) in enumerate(zip(tabs, images, captions)):
            with tab:
                display_zoomable_image(image_data, caption, f"gallery_{i}")
    else:
        display_zoomable_image(images[0], captions[0], "single_0")
