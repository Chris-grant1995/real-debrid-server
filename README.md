# Real-Debrid UI

This project provides a web-based user interface to interact with Real-Debrid, allowing you to add magnet links or torrent files, track their download status, and stream/download files served via rclone.

## Features

*   **Add Torrents:** Easily add new torrents using magnet links or by uploading `.torrent` files.
*   **Status Tracking:** Monitor the progress and status of your Real-Debrid downloads.
*   **Rclone Integration:** Once a torrent is downloaded and available on rclone, browse its contents and stream/download files directly through the UI.
*   **Dynamic Links:** Rclone links are dynamically generated and displayed only when the content is ready and accessible.
*   **Torrent Management:** Remove torrents from the local database and optionally from Real-Debrid.
*   **Responsive UI:** Basic responsive design for ease of use.
*   **Error Handling:** Robust handling for Real-Debrid API rate limits and network issues.

## Technologies Used

*   **Frontend:** React (Vite)
*   **Backend:** FastAPI (Python)
*   **Database:** SQLite (for local torrent metadata)
*   **Proxy/File Serving:** rclone
*   **Containerization:** Docker, Docker Compose

## Setup and Installation

This project uses Docker Compose for easy setup and deployment.

### Prerequisites

*   Docker Desktop (or Docker Engine) installed and running.
*   A Real-Debrid account and API key.

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd real-debrid-server
```

### 2. Configure Environment Variables

Create a `.env` file in the root directory of the project based on `.env.example`:

```bash
cp .env.example .env
```

Edit the newly created `.env` file:

*   `REAL_DEBRID_API_KEY`: Your Real-Debrid API key (obtainable from [Real-Debrid API page](https://real-debrid.com/apitoken)).
*   `BACKEND_API_URL`: The base URL for the backend API. For local development, `http://localhost:8000` is typically used.

Example `.env` file:

```env
REAL_DEBRID_API_KEY=YOUR_REAL_DEBRID_API_KEY
BACKEND_API_URL=http://localhost:8000
```

### 3. Configure rclone

You need to configure rclone to connect to your Real-Debrid account.

Create an `rclone.conf` file in `rclone/config/rclone.conf`.

```bash
mkdir -p rclone/config # if it doesn't exist
# Then create rclone/config/rclone.conf with your Real-Debrid remote configuration
```

A basic `rclone.conf` for Real-Debrid might look like this (replace `YOUR_USERNAME` and `YOUR_PASSWORD`):

```ini
[realdebrid]
type = webdav
url = https://dav.real-debrid.com/
vendor = other
user = YOUR_USERNAME
pass = YOUR_PASSWORD # WARNING: Storing passwords in plain text is not secure. Use rclone config --config rclone/config/rclone.conf create realdebrid webdav to create it securely.
```

**Security Warning:** Storing your Real-Debrid password in plain text in `rclone.conf` is generally not recommended for security. For production environments, consider using rclone's secure configuration methods, which encrypt sensitive information. For local development or testing, this might be acceptable.

### 4. Build and Run with Docker Compose

```bash
docker-compose down # Stop any previous running containers
docker-compose up --build # Build images and start containers
```

This command will:
*   Build the `backend` and `frontend` Docker images.
*   Start the `backend` service (FastAPI).
*   Start the `frontend` service (React/Vite dev server).
*   Start the `rclone` service, serving your Real-Debrid WebDAV remote via HTTP on port `8080`.

### 5. Access the Application

Once the containers are up, open your web browser and navigate to:

`http://localhost:5173`

## Usage

*   **Add Magnet/Torrent:** Use the input fields to add magnet links or upload `.torrent` files.
*   **Monitor Status:** The table will display your torrents, their status, and progress.
*   **Browse Files:** For torrents with `Available` status (meaning rclone has detected them), click on the filename to expand and browse the files within.
*   **Download Files:** Click the "Download" button next to a file to initiate a proxied download.
*   **Remove Torrents:** Use the "Remove" button in the Actions column to delete torrents. You will be prompted to choose if you want to remove it only locally or also from Real-Debrid.

## Configuration

### Frontend Environment Variables

The frontend uses Vite environment variables, which are prefixed with `VITE_`.
*   `VITE_BACKEND_API_URL`: The URL where the backend API is accessible. Defaults to `/api` when running within Docker Compose.
*   `VITE_RCLONE_MOUNT_URL`: Base URL for rclone WebDAV mount.

### Backend Environment Variables

*   `REAL_DEBRID_API_KEY`: Your Real-Debrid API key.
*   `BACKEND_API_URL`: The URL where the backend API is running (used internally by Docker Compose for the frontend service to know where to proxy requests during development).

## Troubleshooting

*   **`404 Not Found` for API calls:**
    *   Ensure `VITE_BACKEND_API_URL` is correctly set in your `.env` and `docker-compose.yml`.
    *   Verify the backend container is running and accessible.
*   **`429 Too Many Requests`:**
    *   The backend implements a retry mechanism for `selectFiles`. This indicates Real-Debrid's rate limits are being hit; the system will retry.
*   **Docker Build Errors (`parent snapshot does not exist`):**
    *   Clear your Docker build cache: `docker builder prune -f`
    *   Then rebuild: `docker-compose up --build`
*   **`sqlite3.OperationalError: attempt to write a readonly database`:**
    *   Ensure the `backend` directory has appropriate write permissions for the Docker container. You might try `chmod -R 777 backend` (for debugging purposes) and rebuild.
    *   Delete the local database file: `rm backend/torrents.db` and restart containers.
*   **UI Not Updating / Flickering:**
    *   The UI polls the backend every 10 seconds. Flickering should be minimal. If issues persist, check browser console for errors.

## Contributing

(Optional section: Guidelines for contributions, bug reports, feature requests.)

## License

(Optional section: Project license information.)