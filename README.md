
<h1 align="center">
  <b>Shobana Filter Bot</b>
</h1>

<p align="center">
  A powerful and versatile Telegram bot designed for filtering, automation, and much more!
</p>
<div align="center">
  <a href="https://github.com/mn-bots/ShobanaFilterBot/stargazers">
    <img src="https://img.shields.io/github/stars/mn-bots/ShobanaFilterBot?color=black&logo=github&logoColor=black&style=for-the-badge" alt="Stars" />
  </a>
  <a href="https://github.com/mn-bots/ShobanaFilterBot/network/members">
    <img src="https://img.shields.io/github/forks/mn-bots/ShobanaFilterBot?color=black&logo=github&logoColor=black&style=for-the-badge" alt="Forks" />
  </a>
  <a href="https://github.com/mn-bots/ShobanaFilterBot">
    <img src="https://img.shields.io/github/repo-size/mn-bots/ShobanaFilterBot?color=skyblue&logo=github&logoColor=blue&style=for-the-badge" alt="Repo Size" />
  </a>
  <a href="https://github.com/mn-bots/ShobanaFilterBot/commits/main">
    <img src="https://img.shields.io/github/last-commit/mn-bots/ShobanaFilterBot?color=black&logo=github&logoColor=black&style=for-the-badge" alt="Last Commit" />
  </a>
  <a href="https://github.com/mn-bots/ShobanaFilterBot">
    <img src="https://img.shields.io/github/contributors/mn-bots/ShobanaFilterBot?color=skyblue&logo=github&logoColor=blue&style=for-the-badge" alt="Contributors" />
  </a>
  <a href="https://github.com/mn-bots/ShobanaFilterBot/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/License-GPL%202.0%20license-blueviolet?style=for-the-badge" alt="License" />
  </a>
  <a href="https://www.python.org/">
    <img src="https://img.shields.io/badge/Written%20in-Python-skyblue?style=for-the-badge&logo=python" alt="Python" />
  </a>
  <a href="https://pypi.org/project/Pyrogram/">
    <img src="https://img.shields.io/pypi/v/pyrogram?color=white&label=pyrogram&logo=python&logoColor=blue&style=for-the-badge" alt="Pyrogram" />
  </a>
</div>


---

## ✨ Features

- ✅ Auto Filter  
- ✅ Manual Filter  
- ✅ IMDB Search and Info  
- ✅ Admin Commands  
- ✅ Broadcast Messages  
- ✅ File Indexing  
- ✅ Inline Search  
- ✅ Random Pics Generator  
- ✅ User and Chat Stats  
- ✅ Ban, Unban, Enable, Disable Commands  
- ✅ File Storage  
- ✅ Auto-Approval for Requests  
- ✅ Shortener Link Support (`/short`)  
- ✅ Feedback System  
- ✅ Font Styling (`/font`)  
- ✅ User Promotion/Demotion  
- ✅ Pin/Unpin Messages  
- ✅ Image-to-Link Conversion
- ✅ Auto Delete
- ✅ Auto Restart
- ✅ Added Keep Alive Function (No need uptimerobot & koyeb sleep problem solved)
---

## 🔧 Variables

### Required
- `BOT_TOKEN`: Obtain via [@BotFather](https://telegram.dog/BotFather).  
- `API_ID`: Get this from [Telegram Apps](https://my.telegram.org/apps).  
- `API_HASH`: Also from [Telegram Apps](https://my.telegram.org/apps).  
- `CHANNELS`: Telegram channel/group usernames or IDs (space-separated).  
- `ADMINS`: Admin usernames or IDs (space-separated).  
- `DATABASE_URI`: MongoDB URI ([Learn More](https://youtu.be/1G1XwEOnxxo)).  
- `DATABASE_NAME`: MongoDB database name ([Learn More](https://youtu.be/Miajl2amrKo)).  
- `LOG_CHANNEL`: Telegram channel for activity logs.  

### Optional
- `PICS`: Telegraph links for images in start message (space-separated).  
- `FILE_STORE_CHANNEL`: Channels for file storage (space-separated).  
- Refer to [info.py](https://github.com/mn-bots/ShobanaFilterBot/blob/main/info.py) for more details.

---

## 🚀 Deployment

### Deploy to Koyeb
<details><summary>Click to Expand</summary>
<p>
<a href="https://app.koyeb.com/deploy?type=git&repository=github.com/mn-bots/ShobanaFilterBot&env[BOT_TOKEN]&env[API_ID]&env[API_HASH]&env[CHANNELS]&env[ADMINS]&env[PICS]&env[LOG_CHANNEL]&env[AUTH_CHANNEL]&env[CUSTOM_FILE_CAPTION]&env[DATABASE_URI]&env[DATABASE_NAME]&env[COLLECTION_NAME]=Telegram_files&env[FILE_CHANNEL]=-1001832732995&env[SUPPORT_CHAT]&env[IMDB]=True&env[IMDB_TEMPLATE]&env[SINGLE_BUTTON]=True&env[AUTH_GROUPS]&env[P_TTI_SHOW_OFF]=True&branch=main&name=telegrambot">
 <img src="https://www.koyeb.com/static/images/deploy/button.svg" alt="Deploy to Koyeb">
</a>
</p>
</details>

### Deploy to VPS
<details>
  <summary>Click to Expand</summary>
  <p>

<pre>bash
git clone https://github.com/mn-bots/ShobanaFilterBot
# Install dependencies
pip3 install -U -r requirements.txt
# Configure variables in info.py and start the bot
python3 bot.py</pre>
</p> </details> <hr>

💬 Support
<p> <a href="https://telegram.dog/mnbots_support" target="_blank"> <img src="https://img.shields.io/badge/Telegram-Group-30302f?style=flat&logo=telegram" alt="Telegram Group"> </a> <a href="https://telegram.dog/mrmntg" target="_blank"> <img src="https://img.shields.io/badge/Telegram-Channel-30302f?style=flat&logo=telegram" alt="Telegram Channel"> </a> </p> <hr>
🙏 Credits
<ul> <li><a href="https://github.com/pyrogram/pyrogram" target="_blank">Dan</a> for the Pyrogram Library</li> <li><a href="https://github.com/Mahesh0253/Media-Search-bot" target="_blank">Mahesh</a> for the Media Search Bot</li> <li><a href="https://github.com/EvamariaTG/EvaMaria" target="_blank">EvamariaTG</a> for the EvaMaria Bot</li> <li><a href="https://github.com/trojanzhex/Unlimited-Filter-Bot" target="_blank">Trojanz</a> for Unlimited Filter Bot</li> <li>Goutham for spell check, ping, and restart features</li> <li>MN-TG for editing and modifying this repository</li> <li> If your intrested to Collab with us Just fork this repo and create pull request ------<a href="https://github.com/MN-BOTS/ShobanaFilterBot/fork" target="_blank"> Click Here To Fork Repo  </a></li> </ul> <hr>
📜 Disclaimer
<p> <a href="https://www.gnu.org/licenses/agpl-3.0.en.html" target="_blank"> <img src="https://www.gnu.org/graphics/agplv3-155x51.png" alt="GNU AGPLv3"> </a> </p> <p> This project is licensed under the <a href="https://github.com/mn-bots/ShobanaFilterBot/blob/main/LICENSE" target="_blank">GNU AGPL 3.0</a>. <strong>Selling this code for monetary gain is strictly prohibited.</strong> </p> <hr> ```

## AI Movie Discovery

AI discovery is intentionally separate from file search. Configure `OPENAI_API_KEY` in the deployment environment to enable the primary OpenAI web-search path. Optional settings are `OPENAI_MODEL` (default `gpt-4.1-mini`) and `AI_SEARCH_TIMEOUT` (default `35`).

A discovery request such as `Duniya Vijay movies` first produces movie-name/year buttons from public movie information. The bot does not inspect its MongoDB Media collection at this stage. The existing file database is queried only after the user clicks a movie button.
