import os
import re
import datetime
import requests
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# Define the absolute path to the log file (adjust if necessary)
LOG_FILE = os.path.join(os.path.dirname(__file__), 'messages_log.txt')

# A sample phonebook mapping (update with actual mappings)
PHONEBOOK = {
    "whatsapp:+18494561575": "Alex P",
    "whatsapp:+1234567890": "John Doe",
    # Add additional mappings as needed.
}

def filter_logs_for_query(query, log_lines):
    """
    Filters log entries based on the query.
    For example, if the query mentions "past X days", only include entries from that period.
    Also only include lines that contain the query text (case‑insensitive).
    """
    cutoff = None
    m = re.search(r'past (\d+) days', query, re.IGNORECASE)
    if m:
        days = int(m.group(1))
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=days)
    
    filtered = []
    for line in log_lines:
        include_line = True
        
        # If a cutoff date is determined, only include entries newer than the cutoff.
        if cutoff:
            try:
                # Assuming each log line starts with "Time: YYYY-MM-DD HH:MM:SS, ..."
                time_str = line.split(',')[0].replace("Time: ", "").strip()
                entry_time = datetime.datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                if entry_time < cutoff:
                    include_line = False
            except Exception:
                pass
        
        # Also, require that the line contains some text from the query.
        if query.lower() not in line.lower():
            include_line = False

        if include_line:
            filtered.append(line)
    
    # Fallback: if nothing matches, return all lines.
    if not filtered:
        filtered = log_lines
    return filtered

import json
import requests

def query_ollama(prompt):
    """
    Sends the prompt to the local LLM via the Ollama API using the /api/chat endpoint.
    Handles streaming JSON lines by iterating over each line in the response.
    """
    url = "http://localhost:11434/api/chat"  # endpoint that worked in your terminal
    payload = {
        "model": "llama2",  # adjust if needed
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 500,
        "temperature": 0.7,
    }
    try:
        # Enable streaming so that we can iterate over lines as they are received.
        response = requests.post(url, json=payload, stream=True)
        if response.status_code == 200:
            answer_parts = []
            # Iterate over each line in the streaming response.
            for line in response.iter_lines():
                if line:  # avoid empty lines
                    try:
                        # Each line is a separate JSON object.
                        data = json.loads(line.decode("utf-8"))
                        # If the line contains a message with content, append it.
                        if "message" in data and "content" in data["message"]:
                            answer_parts.append(data["message"]["content"])
                    except Exception as e:
                        # You can log this error if needed.
                        print(f"Error parsing line: {e}")
            # Join all parts to form the complete answer.
            return "".join(answer_parts).strip()
        else:
            return f"Error: Received status code {response.status_code}"
    except Exception as e:
        return f"Error querying LLM: {str(e)}"


####################################
# Chat UI and Query Endpoints
####################################

@app.route('/chat')
def chat():
    """
    Renders a simple chat interface.
    """
    html = """
    <!DOCTYPE html>
    <html>
    <head>
      <title>LLM Chat Interface</title>
      <style>
         body { font-family: Arial, sans-serif; margin: 20px; }
         #chat-box { border: 1px solid #ccc; padding: 10px; height: 400px; overflow-y: scroll; }
         .user { color: blue; margin: 5px 0; }
         .assistant { color: green; margin: 5px 0; }
         .message { margin-bottom: 10px; }
      </style>
    </head>
    <body>
      <h1>LLM Chat Interface</h1>
      <div id="chat-box"></div>
      <form id="chat-form">
        <input type="text" id="user-input" placeholder="Enter your query..." style="width:80%;" required>
        <button type="submit">Send</button>
      </form>
      <script>
        const form = document.getElementById("chat-form");
        const chatBox = document.getElementById("chat-box");
        
        function appendMessage(cls, text) {
          const div = document.createElement("div");
          div.className = "message " + cls;
          div.textContent = text;
          chatBox.appendChild(div);
          chatBox.scrollTop = chatBox.scrollHeight;
        }
        
        form.addEventListener("submit", async (e) => {
          e.preventDefault();
          const inputField = document.getElementById("user-input");
          const userQuery = inputField.value;
          inputField.value = "";
          appendMessage("user", "User: " + userQuery);
          try {
            const response = await fetch("/chat/query", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ query: userQuery })
            });
            const data = await response.json();
            appendMessage("assistant", "Assistant: " + data.answer);
          } catch (err) {
            console.error("Error:", err);
            appendMessage("assistant", "Assistant: Error processing your query.");
          }
        });
      </script>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route('/chat/query', methods=['POST'])
def chat_query():
    """
    Receives the query from the chat UI, reads and filters the log file,
    builds a prompt for the LLM, and returns the LLM's answer as JSON.
    """
    data = request.get_json()
    if not data or 'query' not in data:
        return jsonify({"answer": "No query provided."}), 400
    query = data['query']

    # Read the log file.
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            log_lines = f.readlines()
    else:
        log_lines = []

    filtered_logs = filter_logs_for_query(query, log_lines)
    phonebook_str = "\n".join([f"{num} -> {name}" for num, name in PHONEBOOK.items()])
    logs_text = "".join(filtered_logs)

    # Build the prompt. You might choose to include the log information in the prompt
    # if it’s relevant to the query. For simplicity, here we only send the query.
    prompt = f"""You are a helpful assistant summarizing employee progress updates.
Below is a table mapping phone numbers to employee names:
{phonebook_str}

Below are the relevant log entries:
{logs_text}

Answer the following question concisely:
{query}
"""
    answer = query_ollama(prompt)
    return jsonify({"answer": answer})

####################################
# Run the Chat UI Application
####################################

if __name__ == '__main__':
    # Run on port 5001 (or change as needed).
    app.run(host='0.0.0.0', port=5001, debug=True)
