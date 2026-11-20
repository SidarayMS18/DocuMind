"""
Context viewer component for displaying expanded text context around highlights.
"""

import streamlit as st
from typing import Dict, Any, Optional


def display_context_modal(source: Dict[str, Any], full_context: Optional[str] = None):
    """
    Display a modal-like expandable section with full context around highlighted text.
    
    Args:
        source: Source attribution dictionary
        full_context: Optional full context text (if available from API)
    """
    with st.expander("📖 View full context", expanded=False):
        st.markdown("### Document Context")
        
        # Display metadata
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Document", source['document_name'])
        with col2:
            st.metric("Page", source['page_number'])
        with col3:
            st.metric("Relevance", f"{source['relevance_score']:.1%}")
        
        st.divider()
        
        # Display the text excerpt with highlighting
        st.markdown("#### Highlighted Excerpt")
        st.info(source['text_excerpt'])
        
        # Display full context if available
        if full_context:
            st.markdown("#### Full Page Context")
            st.text_area(
                "Full text from this page",
                value=full_context,
                height=300,
                disabled=True
            )
        else:
            st.caption("Full context not available. Showing excerpt only.")


def display_interactive_source_card(
    source: Dict[str, Any],
    on_click_callback: Optional[callable] = None
):
    """
    Display an interactive source card that can be clicked to expand.
    
    Args:
        source: Source attribution dictionary
        on_click_callback: Optional callback function when card is clicked
    """
    # Create a clickable card using columns for layout
    with st.container():
        col1, col2 = st.columns([4, 1])
        
        with col1:
            st.markdown(f"""
            **📄 {source['document_name']}** - Page {source['page_number']}
            
            *Relevance: {source['relevance_score']:.2%}*
            """)
        
        with col2:
            if st.button("Expand", key=f"expand_{source.get('id', 'unknown')}"):
                if on_click_callback:
                    on_click_callback(source)
                else:
                    display_context_modal(source)


def create_source_navigation(sources: list):
    """
    Create a navigation interface for multiple sources.
    
    Args:
        sources: List of source attribution dictionaries
    """
    if not sources:
        st.info("No sources available")
        return
    
    st.markdown("### 📚 Source Navigation")
    
    # Create a selectbox for source navigation
    source_options = [
        f"{i+1}. {s['document_name']} (Page {s['page_number']})"
        for i, s in enumerate(sources)
    ]
    
    selected_idx = st.selectbox(
        "Jump to source:",
        range(len(sources)),
        format_func=lambda i: source_options[i]
    )
    
    if selected_idx is not None:
        selected_source = sources[selected_idx]
        display_context_modal(selected_source)


def display_source_comparison(sources: list):
    """
    Display multiple sources side-by-side for comparison.
    
    Args:
        sources: List of source attribution dictionaries
    """
    if len(sources) < 2:
        st.info("Need at least 2 sources for comparison")
        return
    
    st.markdown("### 🔄 Compare Sources")
    
    # Create columns for side-by-side comparison
    cols = st.columns(min(len(sources), 3))
    
    for idx, (col, source) in enumerate(zip(cols, sources[:3])):
        with col:
            st.markdown(f"**Source {idx + 1}**")
            st.caption(f"{source['document_name']}")
            st.caption(f"Page {source['page_number']}")
            st.progress(source['relevance_score'])
            
            with st.expander("View excerpt"):
                st.text(source['text_excerpt'][:200] + "...")
    
    if len(sources) > 3:
        st.info(f"Showing 3 of {len(sources)} sources. Scroll down to see all.")
