# llmchat

This program provides a window GUI chat interface to OpenAI ChatGPT. 
Advantages compared to the web interface :
* You can estimate tokens to be sent (prompt) by clicking *check # Tokens*
* You can follow the token consumption of the previous iteration and the cumulative total (for fee estimation)
* You can submit either as "User" or "System" prompts
* You can select the temperature f the model (the amount displayed is divided by 100, so 100 means Temperature=1)
* You can load and save chat sessions in JSON format (which also allows for offline viewing and edition using a text editor)

Remarks : 
- Before starting, you need to create a python virtual environment according to requirements.txt using `pip install -r requirements.txt`
- your OpenAI API KEY needs to be stored in a .env file in the same directory as the llmchat.py file
- Please type "python llmchat.py" to start the program
- the subdirectory "chats" is available to store chats (but you may use another location)

