# MoveIt ✨

A powerful, safe, and intuitive Discord bot for advanced message management. Designed for server moderators who need precise control over cleaning, splitting, and merging conversations.

> **Core Philosophy:** MoveIt is built with safety as a priority. It is disabled by default and requires an administrator to perform a one-time setup, ensuring server owners have full control from the very beginning.

---

## Key Features

*   **Mandatory Secure Setup:** The bot will not operate until an administrator configures it with the `/setup` command, designating logging channels and user roles.
*   **Detailed Audit Logging:** Every move action is recorded in a designated private channel, providing a clear and permanent record of moderator activity.
*   **Intuitive "Move Queue" System:** For messy, interleaved conversations, moderators can right-click messages to add them to a temporary "shopping cart" and move them all at once.
*   **Powerful Command Suite:**
    *   **Right-Click to Move:** The fastest way to handle a single misplaced message.
    *   `/split`: Extract a continuous block of conversation to a new channel or thread.
    *   `/merge`: Move all messages from one channel into another, with safety confirmations for destructive actions.
    *   `/movebyuser`: Clean up all messages from a specific user in a channel.
*   **Role-Based Permissions:** Access is restricted to server Administrators and any additional roles you explicitly grant permission to.

---

## Installation & Setup Guide

Follow these steps to get your own instance of MoveIt running.

### Prerequisites

*   Python 3.8 or newer
*   Git

### 1. Clone the Repository

Open your terminal and clone this repository to your local machine.
```bash
git clone https://github.com/your-username/MoveIt.git
cd MoveIt
```

### 2. Create the Environment File
The bot's secret token is stored in a .env file. Create this file in the root of the project directory.

⚠️ Important: Your Discord Bot Token is a secret. Never commit it to GitHub or share it publicly. The included .gitignore file is already configured to ignore .env files.
Create a file named .env and add the following:

.env
DISCORD_TOKEN=YOUR_BOT_TOKEN_HERE
DB_PATH=settings.db
LOG_PATH=moveit.log
Use code with caution.
You can get your DISCORD_TOKEN from the Discord Developer Portal.
3. Install Dependencies
Install all the required Python libraries using the requirements.txt file. It's highly recommended to do this within a virtual environment.
Generated bash
# Create and activate a virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`

# Install dependencies
```bash
pip install -r requirements.txt
```

4. Run the Bot
You can now start the bot with the following command:
Generated bash
python move_it.py
Use code with caution.
Bash
If everything is configured correctly, you will see a "Logged in as..." message in your terminal, and the bot will appear online in Discord.
In-Server Configuration
Before the bot can be used, an Administrator must run the /setup command.
/setup
Configures MoveIt for this server. This must be run before any other command will work.
audit_log_channel (Required): The private text channel where all move actions will be logged.
additional_roles (Optional): Grant non-admin roles (e.g., @Moderator) permission to use MoveIt's commands.
Command Reference
The Move Queue System
This workflow is designed for cleaning up messy, interleaved conversations.
1. Right-Click -> Apps -> Add to Move Queue
Adds a single message to your personal move queue. Use this on multiple messages across a channel.
2. /queue view
Shows you a private list of the messages currently in your queue.
3. /queue clear
Empties your queue without moving any messages.
4. /queue move
Moves all messages from your queue to a new location.
target_channel: The destination channel.
thread_name (Optional): Creates a new thread for the moved messages.
Single, Block, and User Moves
Right-Click -> Apps -> Move Message
The fastest way to move a single message. A pop-up will ask for the target channel.
/split
Moves a continuous block of messages.
first_message_id: The starting message of the block.
last_message_id (Optional): The ending message of the block. If omitted, only the first message is moved.
target_channel: The destination channel.
thread_name (Optional): Creates a new thread for the block.
/movebyuser
Moves all messages by a specific member from a channel.
user: The user whose messages to move.
source_channel: The channel to search in.
target_channel: The destination channel.
time_limit (Optional): Filter messages from the "Last Hour", "Last 24 Hours", etc.
Channel-Level Commands
/merge
Moves all messages from one channel into another.
source_channel: The channel to empty.
target_channel: The destination channel.
delete_source_channel (Optional): Deletes the source channel after a successful merge. A confirmation prompt will appear for this action.
Permissions
Administrators have access to all MoveIt commands by default, provided /setup has been completed.
Users with roles specified in the additional_roles option during setup can also use all commands.