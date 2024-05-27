import os
import uvicorn
from uvicorn.config import LOGGING_CONFIG

from file_monitor import WatchdogThread, UpdateThread
from memory_server import app, server_state
from settings import *

if __name__ == "__main__":

    watchdog_thread = WatchdogThread(CHAT_PATH, NOTE_PATH)
    watchdog_thread.start()
    update_thread = UpdateThread(server_state)
    update_thread.start()

    LOGGING_CONFIG["formatters"]["access"]["fmt"] = "%(asctime)s %(levelprefix)s %(message)s"
    LOGGING_CONFIG["formatters"]["access"]["datefmt"] = "%Y-%m-%d %H:%M:%S"
    uvicorn.run(app, host=os.getenv("HOST", "localhost"), port=os.getenv("PORT", 5000))