import streamlit as st
import streamlit.components.v1 as components
from utils import get_game_html

# Page Configuration
st.set_page_config(
    page_title="Auditorium Seating Simulation",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for the header
st.markdown("""
    <style>
    .main-header {
        font-size: 1.5rem;
        font-weight: bold;
        margin-bottom: 1rem;
    }
    .anycoder-link {
        font-size: 0.8rem;
        color: #666;
        text-decoration: none;
    }
    .anycoder-link:hover {
        text-decoration: underline;
        color: #333;
    }
    </style>
    """, unsafe_allow_html=True)

# Header Section
col1, col2 = st.columns([3, 1])
with col1:
    st.markdown('<div class="main-header">🎓 Auditorium Seating Simulation</div>', unsafe_allow_html=True)
with col2:
    st.markdown('<div style="text-align: right;"><a href="https://huggingface.co/spaces/akhaliq/anycoder" target="_blank" class="anycoder-link">Built with anycoder</a></div>', unsafe_allow_html=True)

# Sidebar Instructions
with st.sidebar:
    st.header("Instructions")
    st.markdown("""
    **Objective:** Fill all 250 seats efficiently.
    
    **Legend:**
    - ⬜ **White/Grey:** Empty Seat
    - 🟥 **Red:** Occupied Seat
    - 🔵 **Blue Dot:** Student
    - 🚪 **Green:** Entrances
    
    **Movement Mechanics:**
    - Students spawn at 1 of 3 random back entrances.
    - **Aisles:** 100% Speed
    - **Empty Seats:** 75% Speed
    - **Occupied Seats:** 25% Speed (Congestion)
    
    **Controls:**
    Use the buttons inside the game window to Start or Reset the simulation.
    """)
    
    st.info("Note: This simulation uses a custom HTML5 Canvas engine embedded in Streamlit to achieve 60FPS smooth animations.")

# Main Game Container
# We inject the HTML/JS game engine here.
# The game logic handles the timer, pathfinding, and rendering internally to ensure performance.
game_html = get_game_html()

components.html(game_html, height=850, scrolling=False)

