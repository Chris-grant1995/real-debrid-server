from fastapi import FastAPI, HTTPException, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
import os
import requests
import urllib.parse
from dotenv import load_dotenv
from pydantic import BaseModel
import asyncio
import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi.responses import StreamingResponse
import database
from database import SessionLocal, engine, Torrent, create_db_and_tables

load_dotenv()

app = FastAPI()

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REAL_DEBRID_API_KEY = os.getenv("REAL_DEBRID_API_KEY")
REAL_DEBRID_BASE_URL = "https://api.real-debrid.com/rest/1.0"

if not REAL_DEBRID_API_KEY:
    print("WARNING: REAL_DEBRID_API_KEY environment variable not set.")

def _make_rd_request(method: str, path: str, **kwargs):
    headers = kwargs.pop("headers", {})
    headers["Authorization"] = f"Bearer {REAL_DEBRID_API_KEY}"
    url = f"{REAL_DEBRID_BASE_URL}{path}"
    response = requests.request(method, url, headers=headers, **kwargs)
    response.raise_for_status()
    if response.status_code == 204:
        return None
    return response.json()

from bs4 import BeautifulSoup

def _get_rclone_listing(rclone_base_path: str):
    """
    Fetches an rclone directory listing and parses it.
    rclone_base_path should be like 'torrents/Some.Movie.1080p/'
    """
    full_url = f"http://rclone:8080/{rclone_base_path}"
    try:
        response = requests.get(full_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        files_and_dirs = []
        # Find all <a> tags that are children of <td> within a table (common rclone http serve styling)
        # Or simply find all <a> tags for broader compatibility
        for a_tag in soup.find_all('a'):
            href = a_tag.get('href')
            if href and href != '../': # Ignore parent directory link
                name = a_tag.text.strip()
                if name.endswith('/') or (href.endswith('/') and not name.endswith('/')):
                    file_type = 'directory'
                    name = name.rstrip('/') # Remove trailing slash for name
                    href = href.rstrip('/') + '/' # Ensure trailing slash for directory href
                else:
                    file_type = 'file'
                
                # Check for empty name or irrelevant entries
                if name and name != '.' and name != '..':
                    # If it's a file, check for extension
                    if file_type == 'file':
                        name_without_query = name.split('?')[0] # Remove query params if any
                        _, ext = os.path.splitext(name_without_query)
                        if not ext: # If no extension, skip this entry
                            continue 
                    
                    files_and_dirs.append({
                        'name': name, 
                        'type': file_type, 
                        'path': urllib.parse.unquote(href) # Unquote href for consistency
                    })
        return files_and_dirs
    except requests.exceptions.RequestException as e:
        print(f"Error fetching rclone listing for {full_url}: {e}")
        return []

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def update_torrents_status():
    while True:
        await asyncio.sleep(15)  # Run every 15 seconds
        db = SessionLocal()
        try:
            torrents = db.query(Torrent).all()
            
            for torrent in torrents:
                updated = False # Flag to commit changes

                # --- Step 1: Always attempt to get the latest status and full info from Real-Debrid ---
                # This applies to any torrent not yet 'downloaded'
                if torrent.status != "downloaded":
                    try:
                        info = _make_rd_request("GET", f"/torrents/info/{torrent.id}")
                        
                        # Update all relevant fields if they were placeholders or changed
                        if torrent.filename in ("Fetching info...", "N/A"): # For newly added torrents
                            torrent.filename = info.get("filename", torrent.filename)
                            torrent.hash = info.get("hash", torrent.hash)
                            torrent.bytes = info.get("bytes", torrent.bytes)
                            torrent.host = info.get("host", torrent.host)
                            torrent.split = info.get("split", torrent.split)
                            updated = True
                            print(f"Updated full info for torrent {torrent.id}: new status {info.get('status')}")

                        # Update status, progress, links from RD
                        current_rd_status = info.get("status", torrent.status)
                        if torrent.status != current_rd_status:
                            torrent.status = current_rd_status
                            updated = True
                        if torrent.progress != info.get("progress", torrent.progress):
                            torrent.progress = info.get("progress", torrent.progress)
                            updated = True
                        if info.get("links") and torrent.links != info.get("links"):
                            torrent.links = info.get("links")
                            updated = True

                    except requests.exceptions.RequestException as e:
                        if e.response is not None and e.response.status_code == 404:
                            # Torrent info not yet available. This is an expected transient state for new torrents.
                            pass
                        else:
                            print(f"Error updating torrent {torrent.id}: {e}")
                        
                        if updated: # Commit any partial updates (e.g., filename from RD if 404 on subsequent info fetches)
                            db.commit()
                        continue # Skip to next torrent if RD info fetch failed, as we can't proceed without current info.

                    # --- Step 2: If torrent is still "waiting_files_selection" AFTER fetching latest info, attempt to select files ---
                    if torrent.status == "waiting_files_selection":
                        retry_attempts = 0
                        max_retries = 10 # Allow more retries for 429 errors
                        retry_delay_seconds = 5 # Initial delay
                        while retry_attempts < max_retries:
                            try:
                                _make_rd_request("POST", f"/torrents/selectFiles/{torrent.id}", data={"files": "all"})
                                print(f"Successfully sent selectFiles for torrent {torrent.id}")
                                updated = True
                                break # Exit retry loop on success
                            except requests.exceptions.RequestException as e:
                                if e.response is not None and e.response.status_code == 429:
                                    retry_attempts += 1
                                    print(f"Rate limit hit for selectFiles {torrent.id}. Attempt {retry_attempts}/{max_retries}. Retrying in {retry_delay_seconds}s...")
                                    await asyncio.sleep(retry_delay_seconds)
                                    # Optional: implement exponential backoff
                                    # retry_delay_seconds = min(60, retry_delay_seconds * 1.5) 
                                else:
                                    print(f"Error selecting files for torrent {torrent.id}: {e}")
                                    break # Exit retry loop for other errors
                            finally:
                                # Ensure db.commit() happens even if `selectFiles` loop breaks early
                                if updated:
                                    db.commit()
                                    updated = False # Reset to avoid double commit if outer loop also commits
                        if retry_attempts >= max_retries:
                            print(f"Failed to select files for torrent {torrent.id} after {max_retries} attempts due to 429 errors.")
                        continue # Continue to next torrent after retry attempts (either success or failure)

                # --- Step 3: Check rclone availability (only for downloaded torrents not yet available) ---
                if torrent.status == "downloaded" and not torrent.rclone_available:
                    try:
                        encoded_filename = urllib.parse.quote(torrent.filename)
                        rclone_url = f"http://rclone:8080/torrents/{encoded_filename}/"
                        resp = requests.head(rclone_url, timeout=5)
                        if resp.status_code == 200:
                            torrent.rclone_available = True
                            torrent.rclone_available_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
                            updated = True
                    except Exception:
                        pass # Ignore connection errors or timeouts, will retry next loop
                
                if updated:
                    db.commit()
        finally:
            db.close()

@app.on_event("startup")
async def startup_event():
    create_db_and_tables()
    asyncio.create_task(update_torrents_status())

@app.get("/api/torrents/recent")
def get_recent_torrents(db: Session = Depends(get_db)):
    return db.query(Torrent).order_by(Torrent.added.desc()).all()

class MagnetLink(BaseModel):
    magnet: str

@app.post("/api/torrents/add-magnet")
def add_magnet_link(magnet_link: MagnetLink, db: Session = Depends(get_db)):
    if not REAL_DEBRID_API_KEY:
        raise HTTPException(status_code=400, detail="Real-Debrid API key not set.")
    try:
        add_magnet_response = _make_rd_request("POST", "/torrents/addMagnet", data={"magnet": magnet_link.magnet})
        torrent_id = add_magnet_response["id"]
        
        # Create a minimal torrent entry. The background task will update full info.
        new_torrent = Torrent(
            id=torrent_id,
            filename="Fetching info...", # Placeholder
            hash=add_magnet_response.get("hash", "N/A"), # Real-Debrid sometimes returns hash here
            bytes=0, # Placeholder
            host="real-debrid.com",
            split=0, # Placeholder
            progress=0,
            status="waiting_files_selection", # Initial status
            added=datetime.datetime.now(datetime.timezone.utc).isoformat(), # Use current time
            # ended and links will be set by the background task
        )
        db.add(new_torrent)
        db.commit()

        return {"message": "Magnet link added successfully", "torrent_id": torrent_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")

@app.post("/api/torrents/add-file")
async def add_torrent_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not REAL_DEBRID_API_KEY:
        raise HTTPException(status_code=400, detail="Real-Debrid API key not set.")
    try:
        file_content = await file.read()
        add_torrent_response = _make_rd_request("PUT", "/torrents/addTorrent", files={"file": (file.filename, file_content, file.content_type)})
        torrent_id = add_torrent_response["id"]

        # Create a minimal torrent entry. The background task will update full info.
        new_torrent = Torrent(
            id=torrent_id,
            filename=file.filename, # Use original file name as placeholder
            hash=add_torrent_response.get("hash", "N/A"),
            bytes=0, # Placeholder
            host="real-debrid.com",
            split=0, # Placeholder
            progress=0,
            status="waiting_files_selection", # Initial status
            added=datetime.datetime.now(datetime.timezone.utc).isoformat(), # Use current time
            # ended and links will be set by the background task
        )
        db.add(new_torrent)
        db.commit()
        
        return {"message": "Torrent file added successfully", "torrent_id": torrent_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")

@app.get("/api/torrents/{torrent_id}/files")
def get_torrent_files(torrent_id: str, db: Session = Depends(get_db)):
    torrent = db.query(Torrent).filter(Torrent.id == torrent_id).first()
    if not torrent:
        raise HTTPException(status_code=404, detail="Torrent not found.")
    
    if not torrent.rclone_available:
        raise HTTPException(status_code=400, detail="Rclone link not available for this torrent.")

    # Construct the rclone path based on the torrent's filename
    encoded_filename = urllib.parse.quote(torrent.filename)
    rclone_base_path = f"torrents/{encoded_filename}/" # Assuming structure is /torrents/filename/

    files = _get_rclone_listing(rclone_base_path)
    if not files and torrent.status == "downloaded" and torrent.rclone_available:
        # If rclone reports no files, but it should be available, it might be a temporary issue
        # or the folder is empty. For now, we'll return an empty list.
        print(f"Warning: Rclone returned no files for {torrent.filename} ({torrent.id}) but marked as available.")

    return files

@app.get("/api/torrents/{torrent_id}/stream/{file_path:path}")
async def stream_torrent_file(torrent_id: str, file_path: str, db: Session = Depends(get_db)):
    torrent = db.query(Torrent).filter(Torrent.id == torrent_id).first()
    if not torrent:
        raise HTTPException(status_code=404, detail="Torrent not found.")
    
    if not torrent.rclone_available:
        raise HTTPException(status_code=400, detail="Rclone link not available for this torrent.")

    # Construct the full URL to the file on the rclone WebDAV server
    # file_path comes unquoted, but we need to ensure the base path is encoded correctly.
    encoded_filename = urllib.parse.quote(torrent.filename)
    # The file_path itself might contain slashes which are part of the path, not URL delimiters
    # urllib.parse.quote(file_path, safe='') encodes everything, which is what we want for path segments
    full_rclone_file_url = f"http://rclone:8080/torrents/{encoded_filename}/{file_path}"

    try:
        # Use stream=True to avoid loading the whole file into memory
        r = requests.get(full_rclone_file_url, stream=True, timeout=30)
        r.raise_for_status()

        # Determine content type (optional but good practice)
        content_type = r.headers.get('Content-Type', 'application/octet-stream')
        # Determine file size (optional but good for progress bars)
        content_length = r.headers.get('Content-Length')

        # Generator to stream the file content
        def iterfile():
            for chunk in r.iter_content(chunk_size=8192):
                yield chunk
        
        headers = {
            "Content-Disposition": f"attachment; filename=\"{os.path.basename(file_path)}\""
        }
        if content_length:
            headers["Content-Length"] = content_length

        return StreamingResponse(iterfile(), media_type=content_type, headers=headers)
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Failed to stream file from rclone: {e}")

@app.delete("/api/torrents/{torrent_id}")
def delete_torrent(torrent_id: str, remove_from_rd: bool = False, db: Session = Depends(get_db)):
    if not REAL_DEBRID_API_KEY:
        raise HTTPException(status_code=400, detail="Real-Debrid API key not set.")
    
    torrent_to_delete = db.query(Torrent).filter(Torrent.id == torrent_id).first()
    if not torrent_to_delete:
        raise HTTPException(status_code=404, detail="Torrent not found in local database.")

    if remove_from_rd:
        try:
            _make_rd_request("DELETE", f"/torrents/delete/{torrent_id}")
            print(f"Successfully deleted torrent {torrent_id} from Real-Debrid.")
        except requests.exceptions.RequestException as e:
            print(f"Error deleting torrent {torrent_id} from Real-Debrid: {e}")
            # Do not re-raise, proceed with local deletion even if RD fails

    db.delete(torrent_to_delete)
    db.commit()

    return {"message": f"Torrent {torrent_id} deleted successfully."}
