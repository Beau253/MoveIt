# gdrive_handler.py
import io
import json
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

SCOPES = ['https://www.googleapis.com/auth/drive']
DB_FILENAME = 'settings.db'

def get_drive_service(credentials_json_string):
    print("[GDRIVE_HANDLER][GET_SERVICE] Authenticating with Google...")
    try:
        creds_info = json.loads(credentials_json_string)
        creds = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
        service = build('drive', 'v3', credentials=creds)
        print("[GDRIVE_HANDLER][GET_SERVICE] Authentication successful.")
        return service
    except Exception as e:
        print(f"[GDRIVE_HANDLER][GET_SERVICE] ❌ FAILED to authenticate with Google: {e}")
        return None

def sync_with_gdrive(credentials, folder_id, local_db_path):
    print("[GDRIVE_HANDLER][SYNC] Starting GDrive sync...")
    service = get_drive_service(credentials)
    if not service:
        print("[GDRIVE_HANDLER][SYNC] ❌ Cannot sync without a valid GDrive service.")
        return

    print("[GDRIVE_HANDLER][SYNC] Checking for existing DB file on GDrive...")
    query = f"'{folder_id}' in parents and name = '{DB_FILENAME}'"
    response = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    files = response.get('files', [])

    if not files:
        print("[GDRIVE_HANDLER][SYNC] No remote DB found. If local DB exists, it will be uploaded.")
        if os.path.exists(local_db_path):
             upload_db(service, folder_id, local_db_path)
    else:
        print("[GDRIVE_HANDLER][SYNC] Remote DB found. Downloading...")
        file_id = files[0].get('id')
        request = service.files().get_media(fileId=file_id)
        fh = io.FileIO(local_db_path, 'wb')
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"[GDRIVE_HANDLER][SYNC] Download progress: {int(status.progress() * 100)}%.")
        print("[GDRIVE_HANDLER][SYNC] ✅ Download complete.")

def upload_db(service, folder_id, local_db_path):
    print("[GDRIVE_HANDLER][UPLOAD] Starting DB upload...")
    if not os.path.exists(local_db_path):
        print("[GDRIVE_HANDLER][UPLOAD] ❌ Local DB file does not exist. Cannot upload.")
        return

    query = f"'{folder_id}' in parents and name = '{DB_FILENAME}'"
    response = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    files = response.get('files', [])
    
    media = MediaFileUpload(local_db_path, mimetype='application/x-sqlite3')

    try:
        if not files:
            print("[GDRIVE_HANDLER][UPLOAD] Remote file not found. Creating new file...")
            file_metadata = {'name': DB_FILENAME, 'parents': [folder_id]}
            service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            print("[GDRIVE_HANDLER][UPLOAD] ✅ New file created and uploaded successfully.")
        else:
            file_id = files[0].get('id')
            print(f"[GDRIVE_HANDLER][UPLOAD] Remote file found. Updating file ID {file_id}...")
            service.files().update(fileId=file_id, media_body=media).execute()
            print("[GDRIVE_HANDLER][UPLOAD] ✅ File updated successfully.")
    except Exception as e:
        print(f"[GDRIVE_HANDLER][UPLOAD] ❌ FAILED to upload DB: {e}")