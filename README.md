# BobTheBot
## How to Use .env File for Bot Token and API Key

### Step 1: Create a .env File

1. Create a file ending in  `.env` in the same directory of the python script.
2. Open the `.env` file using a text editor.

### Step 2: Add Environment Variables

1. Add the following lines to the `.env` file

BOT_TOKEN=your_bot_token_here
API_KEY=your_api_key_here


## Server Commands
- **Check if py script is running:**

ps -fA | grep python

- **Terminate py script:**

kill (process-id)

- **Run py script:**
  
nohup /usr/bin/python3 tele.py &

- **Check server datetime:**
  
date

