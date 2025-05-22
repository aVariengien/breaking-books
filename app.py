import streamlit as st
import json
import base64
from io import BytesIO
from PIL import Image
import os
import glob

st.set_page_config(
    page_title="Book Cards Viewer",
    page_icon="📚",
    layout="wide"
)

st.title("📚 Book Cards Viewer")

def get_available_jsonl_files():
    """Get list of all JSONL files in the current directory"""
    return [os.path.basename(f) for f in glob.glob("*.jsonl")]

def load_cards(filename):
    cards = []
    with open(filename, "r") as f:
        for line in f:
            cards.append(json.loads(line))
    return cards

def display_card(card):
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader(card["title"])
        st.write(card["description"])
        
        st.markdown("### Illustration Prompt")
        st.info(card["illustration"])
        
        st.markdown("### Quotes")
        for quote in card["quotes"]:
            st.markdown(f"> {quote}")
    
    with col2:
        if card["image_base64"] != "No image generated":
            # Convert base64 to image
            image_data = base64.b64decode(card["image_base64"])
            image = Image.open(BytesIO(image_data))
            st.image(image, use_column_width=True)
        else:
            st.warning("No image available for this card")

# Get available JSONL files
jsonl_files = get_available_jsonl_files()

if not jsonl_files:
    st.error("No JSONL files found in the current directory.")
else:
    # Add file selector in sidebar
    st.sidebar.markdown("### 📁 Select Cards File")
    selected_file = st.sidebar.selectbox(
        "Choose a JSONL file",
        jsonl_files,
        index=0
    )
    
    # Load and display cards
    try:
        cards = load_cards(selected_file)
        
        # Add a search bar
        search_query = st.text_input("🔍 Search cards by title or description", "")
        
        # Filter cards based on search
        filtered_cards = cards
        if search_query:
            filtered_cards = [
                card for card in cards 
                if search_query.lower() in card["title"].lower() 
                or search_query.lower() in card["description"].lower()
            ]
        
        # Display cards
        for i, card in enumerate(filtered_cards):
            with st.expander(f"Card {i+1}: {card['title']}", expanded=True):
                display_card(card)
            st.markdown("---")
        
        # Display stats
        st.sidebar.markdown("### 📊 Stats")
        st.sidebar.write(f"Total cards: {len(cards)}")
        st.sidebar.write(f"Filtered cards: {len(filtered_cards)}")
        
    except FileNotFoundError:
        st.error(f"File {selected_file} not found.")
    except Exception as e:
        st.error(f"An error occurred: {str(e)}") 