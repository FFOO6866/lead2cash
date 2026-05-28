"""
IPAS SFTP Client

Connects to MTU's secure B2B SFTP server to retrieve IPAS XML order files.
Downloads new files to the local IPAS folder for processing by IPASOrderService.

Server: secure-b2b-dev.mtu-online.com
Path:   /SB2B-SFTP/Integrum/IPAS/
Archive: /SB2B-SFTP/Integrum/IPAS/Archive/

Configuration via environment variables:
    IPAS_SFTP_HOST      - SFTP server hostname
    IPAS_SFTP_PORT      - SFTP port (default: 22)
    IPAS_SFTP_USER      - Username (e.g. fn2\\DPNADM)
    IPAS_SFTP_PASSWORD  - Password
    IPAS_SFTP_PATH      - Remote folder path
    IPAS_SFTP_ARCHIVE   - Remote archive path (move after download)
"""

import logging
import os
import stat
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Defaults matching MTU's B2B server
DEFAULT_SFTP_HOST = "secure-b2b-dev.mtu-online.com"
DEFAULT_SFTP_PORT = 22
DEFAULT_SFTP_PATH = "/SB2B-SFTP/Integrum/IPAS/"
DEFAULT_SFTP_ARCHIVE = "/SB2B-SFTP/Integrum/IPAS/Archive/"


class IPASSFTPClient:
    """SFTP client for retrieving IPAS XML files from MTU's B2B server."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        remote_path: Optional[str] = None,
        archive_path: Optional[str] = None,
        local_folder: Optional[Path] = None,
    ):
        self.host = host or os.getenv("IPAS_SFTP_HOST", DEFAULT_SFTP_HOST)
        self.port = port or int(os.getenv("IPAS_SFTP_PORT", str(DEFAULT_SFTP_PORT)))
        self.username = username or os.getenv("IPAS_SFTP_USER", "")
        self.password = password or os.getenv("IPAS_SFTP_PASSWORD", "")
        self.remote_path = remote_path or os.getenv("IPAS_SFTP_PATH", DEFAULT_SFTP_PATH)
        self.archive_path = archive_path or os.getenv(
            "IPAS_SFTP_ARCHIVE", DEFAULT_SFTP_ARCHIVE
        )
        self.local_folder = (
            local_folder
            or Path(os.getenv("IPAS_XML_FOLDER", ""))
            or Path(__file__).parent.parent / "docs"
        )

        self._transport = None
        self._sftp = None

    @property
    def is_configured(self) -> bool:
        """Check if SFTP credentials are configured."""
        return bool(self.username and self.password and self.host)

    def connect(self) -> bool:
        """Establish SFTP connection.

        Returns:
            True if connected successfully, False otherwise
        """
        if not self.is_configured:
            logger.info(
                "IPAS SFTP not configured (missing IPAS_SFTP_USER/PASSWORD). "
                "Using local folder only."
            )
            return False

        try:
            import paramiko

            self._transport = paramiko.Transport((self.host, self.port))
            self._transport.connect(username=self.username, password=self.password)
            self._sftp = paramiko.SFTPClient.from_transport(self._transport)
            logger.info(
                f"Connected to IPAS SFTP: {self.username}@{self.host}:{self.port}"
            )
            return True
        except ImportError:
            logger.warning("paramiko not installed — SFTP unavailable")
            return False
        except Exception as e:
            logger.warning(f"IPAS SFTP connection failed: {e}")
            self._cleanup()
            return False

    def disconnect(self):
        """Close SFTP connection."""
        self._cleanup()

    def _cleanup(self):
        """Clean up transport and SFTP handles."""
        if self._sftp:
            try:
                self._sftp.close()
            except Exception:
                pass
            self._sftp = None
        if self._transport:
            try:
                self._transport.close()
            except Exception:
                pass
            self._transport = None

    def list_remote_files(self) -> list[str]:
        """List XML files in the remote IPAS folder.

        Returns:
            List of XML filenames found on SFTP server
        """
        if not self._sftp:
            return []

        try:
            entries = self._sftp.listdir_attr(self.remote_path)
            xml_files = [
                entry.filename
                for entry in entries
                if (
                    entry.filename.upper().endswith(".XML")
                    and stat.S_ISREG(entry.st_mode)
                )
            ]
            logger.info(f"SFTP: Found {len(xml_files)} XML files in {self.remote_path}")
            return sorted(xml_files)
        except FileNotFoundError:
            logger.warning(f"SFTP: Remote path not found: {self.remote_path}")
            return []
        except Exception as e:
            logger.error(f"SFTP: Error listing {self.remote_path}: {e}")
            return []

    def download_new_files(self) -> list[Path]:
        """Download new XML files that don't already exist locally.

        Returns:
            List of local paths for newly downloaded files
        """
        if not self._sftp:
            return []

        remote_files = self.list_remote_files()
        if not remote_files:
            logger.info("SFTP: No XML files to download")
            return []

        # Ensure local folder exists
        self.local_folder.mkdir(parents=True, exist_ok=True)

        downloaded = []
        for filename in remote_files:
            local_path = self.local_folder / filename
            if local_path.exists():
                logger.debug(f"SFTP: Skipping {filename} (already exists locally)")
                continue

            try:
                remote_file = self.remote_path.rstrip("/") + "/" + filename
                self._sftp.get(remote_file, str(local_path))
                logger.info(f"SFTP: Downloaded {filename} → {local_path}")
                downloaded.append(local_path)
            except Exception as e:
                logger.error(f"SFTP: Failed to download {filename}: {e}")
                # Clean up partial download
                if local_path.exists():
                    local_path.unlink()

        return downloaded

    def archive_file(self, filename: str) -> bool:
        """Move a processed file to the archive folder on SFTP.

        Args:
            filename: Name of the file to archive

        Returns:
            True if archived successfully
        """
        if not self._sftp:
            return False

        try:
            src = self.remote_path.rstrip("/") + "/" + filename
            dst = self.archive_path.rstrip("/") + "/" + filename

            # Ensure archive folder exists
            try:
                self._sftp.stat(self.archive_path)
            except FileNotFoundError:
                self._sftp.mkdir(self.archive_path)

            self._sftp.rename(src, dst)
            logger.info(f"SFTP: Archived {filename} → {self.archive_path}")
            return True
        except Exception as e:
            logger.error(f"SFTP: Failed to archive {filename}: {e}")
            return False

    def sync(self) -> dict:
        """Full sync: connect, download new files, disconnect.

        Returns:
            Summary dict with counts and file list
        """
        result = {
            "connected": False,
            "remote_files": 0,
            "downloaded": 0,
            "downloaded_files": [],
            "error": None,
        }

        if not self.is_configured:
            result["error"] = "SFTP not configured (missing credentials)"
            return result

        try:
            connected = self.connect()
            result["connected"] = connected

            if not connected:
                result["error"] = f"Could not connect to {self.host}"
                return result

            remote_files = self.list_remote_files()
            result["remote_files"] = len(remote_files)

            downloaded = self.download_new_files()
            result["downloaded"] = len(downloaded)
            result["downloaded_files"] = [str(p) for p in downloaded]

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"SFTP sync error: {e}")
        finally:
            self.disconnect()

        return result

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()

    def __del__(self):
        self._cleanup()
