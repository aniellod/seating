FROM python:3.11-slim

# Set up a user with ID 1000 for HuggingFace Spaces
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

# Copy requirements and install dependencies
COPY --chown=user requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY --chown=user . .

# Expose the port used by HuggingFace Spaces
EXPOSE 7860

# Start the application
CMD ["streamlit", "run", "seating.py", "--server.port=7860", "--server.address=0.0.0.0"]

