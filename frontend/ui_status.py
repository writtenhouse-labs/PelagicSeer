import base64
from pathlib import Path

import streamlit as st


def install_swimming_fish_status(asset_path: Path) -> None:
    """Replace Streamlit's running status glyph with a swimming fish."""
    image_data = base64.b64encode(asset_path.read_bytes()).decode("ascii")
    st.markdown(
        f"""
<style>
div[data-testid="stStatusWidget"] {{
    position: relative;
    width: 8.75rem;
    min-width: 8.75rem;
    height: 2.25rem;
    margin-right: 0.5rem;
}}

div[data-testid="stStatusWidget"] > div {{
    visibility: hidden;
}}

div[data-testid="stStatusWidget"]::before {{
    content: "";
    position: absolute;
    left: 0.25rem;
    top: 0.35rem;
    width: 2.25rem;
    height: 1.4rem;
    background-image: url("data:image/png;base64,{image_data}");
    background-position: center;
    background-repeat: no-repeat;
    background-size: contain;
    animation: pelagic-swim 1.3s ease-in-out infinite;
    transform-origin: center;
}}

div[data-testid="stStatusWidget"]::after {{
    content: "swimming...";
    position: absolute;
    left: 2.8rem;
    top: 0.47rem;
    color: rgb(49, 51, 63);
    font-size: 0.875rem;
    line-height: 1.25rem;
    white-space: nowrap;
}}

@keyframes pelagic-swim {{
    0% {{
        transform: translateX(-0.2rem) rotate(-3deg);
    }}
    50% {{
        transform: translateX(0.35rem) rotate(3deg);
    }}
    100% {{
        transform: translateX(-0.2rem) rotate(-3deg);
    }}
}}
</style>
""",
        unsafe_allow_html=True,
    )
