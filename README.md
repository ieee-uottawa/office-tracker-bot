# Office Tracker Bot

This Discord bot allows users to check in and out of a club office using interactive buttons. It keeps track of who is currently in the office and provides a help command for users. Uses Python 3.12 and py

## Features

- Check in and out of the office
- View current office presence
- Interactive buttons for easy check-in/out
- Manual commands to check in/out
- Help command with usage instructions

## Setup Instructions

### Local Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/office-tracker.git
   cd office-tracker
   ```

2. Create a virtual environment and activate it:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required packages:

   ```bash
   pip install -r requirements.txt
   ```

4. Set your Discord bot token as an environment variable:

   ```bash
   export DISCORD_TOKEN="your_discord_bot_token"
   ```

5. Run the bot:

   ```bash
   python main.py
   ```

## Running with Docker

1. Build the Docker image:

   ```bash
   docker build -t office-tracker-bot .
   ```

2. Run the Docker container, passing your Discord bot token as an environment variable:

   ```bash
   docker run -e DISCORD_TOKEN="your_discord_bot_token" --name office-tracker-bot office-tracker-bot
   ```

## Usage

The bot will update the persistent embed in the specified channel with the current office presence. Users can check in and out using the buttons provided in the embed or by using the slash commands.

### Commands

```bash
/setup - Create persistent embed in current channel (requires administrator permissions)
/add @member - Manually check in a member
/remove @member - Manually check out a member
```

### Environment Variables

- `DISCORD_TOKEN`: Your Discord bot token (required)
- `GUILD_ID`: The ID of the Discord server where the bot will operate (required)
- `OFFICE_TRACKER_CHANNEL_NAME`: The name of the channel where the office tracker dashboard will be posted (default: `office-tracker`)
- `RFID_ENABLED`: Set to `True` to enable RFID TCP server functionality (default: `False`)

## Github Actions Workflow

- This workflow builds and pushes the Docker image to Docker Hub when you create a release on GitHub.
