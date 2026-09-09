from typing import Dict, Any, List, Optional
import io
import stat

import paramiko


class SFTPConnector:
    """
    SFTP File Connector for Wisualyst Platform.
    Connects to a real SFTP host over SSH, scans a remote directory for
    CSV/JSON data feeds, and lets callers pull a discovered file's content
    back for ingestion.
    """
    def __init__(self, host: str = "", port: int = 22, username: str = "", password: str = "", remote_path: str = "/exports/daily_feeds"):
        self.host = host.strip() if host else ""
        self.port = int(port) if port else 22
        self.username = username.strip() if username else ""
        self.password = password.strip() if password else ""
        self.remote_path = remote_path.strip() if remote_path else "/exports/daily_feeds"

    def _connect(self, timeout: float = 10.0) -> paramiko.SFTPClient:
        """Open a real SSH transport and SFTP session. Caller must close it."""
        transport = paramiko.Transport((self.host, self.port))
        try:
            transport.connect(username=self.username, password=self.password)
        except Exception:
            transport.close()
            raise
        return paramiko.SFTPClient.from_transport(transport)

    def test_connection(self) -> Dict[str, Any]:
        """Test SFTP connection parameters against the real host"""
        if not self.host or not self.username:
            return {
                "status": "ERROR",
                "message": "Missing SFTP Server Host or Username. Please fill in SFTP connection details."
            }

        sftp = None
        try:
            sftp = self._connect()
            sftp.listdir(self.remote_path)
            return {
                "status": "SUCCESS",
                "message": f"Successfully authenticated SFTP connection to {self.username}@{self.host}:{self.port}",
                "remote_directory": self.remote_path
            }
        except paramiko.AuthenticationException:
            return {
                "status": "ERROR",
                "message": f"Authentication failed for {self.username}@{self.host}:{self.port}. Check the username and password."
            }
        except FileNotFoundError:
            return {
                "status": "ERROR",
                "message": f"Connected to {self.host}:{self.port}, but remote directory '{self.remote_path}' does not exist."
            }
        except Exception as e:
            return {
                "status": "ERROR",
                "message": f"Could not connect to {self.host}:{self.port}. Details: {str(e)}"
            }
        finally:
            if sftp:
                sftp.close()
                sftp.get_channel().get_transport().close()

    def discover_files(self) -> List[Dict[str, Any]]:
        """Scan the real remote directory for CSV/JSON dataset feeds"""
        if not self.host or not self.username:
            return []

        sftp = None
        try:
            sftp = self._connect()
            discovered = []
            for entry in sftp.listdir_attr(self.remote_path):
                if stat.S_ISDIR(entry.st_mode):
                    continue
                if not (entry.filename.lower().endswith(".csv") or entry.filename.lower().endswith(".json")):
                    continue

                remote_file_path = f"{self.remote_path.rstrip('/')}/{entry.filename}"
                columns = self._peek_columns(sftp, remote_file_path)

                discovered.append({
                    "table_name": entry.filename,
                    "table_key": f"sftp_{entry.filename.rsplit('.', 1)[0]}",
                    "size_bytes": entry.st_size,
                    "columns": columns
                })
            return discovered
        except Exception:
            return []
        finally:
            if sftp:
                sftp.close()
                sftp.get_channel().get_transport().close()

    def fetch_file_content(self, remote_file_path: str) -> str:
        """Download a discovered file's full content as text, for ingestion"""
        sftp = None
        try:
            sftp = self._connect()
            with sftp.open(remote_file_path, "r") as remote_file:
                return remote_file.read().decode("utf-8")
        finally:
            if sftp:
                sftp.close()
                sftp.get_channel().get_transport().close()

    def _peek_columns(self, sftp: paramiko.SFTPClient, remote_file_path: str) -> List[str]:
        """Read just the header line of a CSV file to report its columns"""
        if not remote_file_path.lower().endswith(".csv"):
            return []
        try:
            with sftp.open(remote_file_path, "r") as remote_file:
                header_line = remote_file.readline().decode("utf-8", errors="ignore")
            return [col.strip() for col in header_line.strip().split(",") if col.strip()]
        except Exception:
            return []
