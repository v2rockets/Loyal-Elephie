import os
import threading
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime, timedelta

from llm_utils import digest_simple, digest_markdown
from chroma_doc_manager import doc_manager
from bm25_api import update_corpus

modified_files = {}

class MyEventHandler(FileSystemEventHandler):
    def on_modified(self, event):
        print(f"Change: {event.src_path}")
        if event.src_path.endswith('.md'):
            modified_files[event.src_path] = "on_modified"

    def on_created(self, event):
        print(f"Add: {event.src_path}")
        if event.src_path.endswith('.md'):
            modified_files[event.src_path] = "on_created"

    def on_deleted(self, event):
        print(f"Delete: {event.src_path}")
        if event.src_path.endswith('.md'):
            modified_files[event.src_path] = "on_deleted"

    def on_moved(self, event):
        print(f"Move: {event.src_path} to {event.dest_path}")
        if event.src_path.endswith('.md'):
            modified_files[event.src_path] = "on_deleted"
        if event.dest_path.endswith('.md'):
            modified_files[event.dest_path] = "on_created"

class UpdateThread(threading.Thread):
    def __init__(self, server_state, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.server_state = server_state
        update_corpus() # probably better start in memory server

    def run(self):
        while True:
            if not modified_files:  # If there are no modified files
                time.sleep(60)  # Wait for a minute before checking again
                continue  # Skip the rest of the loop and start the next iteration

            now = datetime.now()
            diff = timedelta(seconds=30)
            if self.server_state["last_use"] and now - self.server_state["last_use"] < diff:  # If the server is used in recently 5 mins
                print("Server is used lately")
                time.sleep(10)  # Wait for a minute before checking again
                continue  # Skip the rest of the loop and start the next iteration
            
            path, event_type = next(iter(modified_files.items()))  # Get the first item
            del modified_files[path]  # Remove the handled file
            print(f"To handle {event_type}: {path}")
            try:
                file = os.path.basename(path)
                title = file.rsplit(".", 1)[0].replace(';', ':')
                if "notes" in path:
                    doc_manager.remove_document_by_name(title)
                else:
                    doc_manager.remove_document(title)

                if event_type in ["on_created", "on_modified"]:
                    if "notes" in path:
                        time_str = str(now)[0:10]
                        print(time_str)
                        digests = digest_markdown(title, path)
                        print(digests)
                        for headers, summary in digests:
                            doc_id = "Note of " + headers
                            doc_manager.add_document(summary, doc_id, other_meta = {"doc_time": time_str, "doc_name":title})
                    else:
                        summary, tag = digest_simple(title, path)
                        digest = f"{title}\n{summary}"
                        if len(tag):
                            digest += '\nOpinion: ' + tag
                        print(digest)
                        if title.startswith("Conversation"):
                            time_str = title.rsplit("on", 1)[1][1:11]
                            doc_manager.add_document(digest, title, other_meta = {"doc_time": time_str})
                        else:
                            print("Warning: Unformatted doc ", title)
            except Exception:
                import traceback
                traceback.print_exc()
                print(f"error handling {event_type}: {path}")

            update_corpus()
            

class WatchdogThread(threading.Thread):
    def __init__(self, chat_path, note_path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.chat_path = chat_path
        self.note_path = note_path
        self.observer = Observer()

    def run(self):
        event_handler = MyEventHandler()
        self.observer.schedule(event_handler, self.chat_path, recursive=False)
        self.observer.schedule(event_handler, self.note_path, recursive=False)
        self.observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.observer.stop()
        self.observer.join()
