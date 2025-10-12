import os
import time
import requests
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

WATCH_DIR = "app"
DEPLOY_HOOK_URL = "https://api.render.com/deploy/srv-d3k42bbipnbc73fj8mmg?key=P77pam5Bl_U"  # kendi URL'ini buraya koy

def deploy():
    print("\n🔄 Değişiklik algılandı, güncelleme gönderiliyor...")
    os.system("git add .")
    os.system(f'git commit -m "auto update {datetime.now().strftime("%H:%M:%S")}"')
    os.system("git push origin main")
    requests.post(DEPLOY_HOOK_URL)
    print("✅ Gönderildi (Render arka planda güncelliyor)...")

class Watcher(FileSystemEventHandler):
    def on_modified(self, event):
        if not event.is_directory:
            deploy()

if __name__ == "__main__":
    print(f"👀 '{WATCH_DIR}' klasörü izleniyor... (Ctrl+C ile durdur)")
    observer = Observer()
    observer.schedule(Watcher(), WATCH_DIR, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        observer.join()
