import time
from typing import Any, Dict, Optional
import requests

class TranscriptionClient:
    """
    Agent-optimized Python SDK for the Transcription API.
    Provides simple, blocking methods to submit, check status, and retrieve results.
    """
    def __init__(self, api_key: str, base_url: str = "http://localhost:8000"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"X-API-Key": self.api_key})

    def submit_job(self, source_url: Optional[str] = None, file_path: Optional[str] = None, model: str = "gemini-2.5-flash") -> Dict[str, Any]:
        """
        Submit a new transcription job from a URL or a local file.
        """
        url = f"{self.base_url}/transcriptions"
        data = {"model": model}
        
        if source_url:
            data["source_url"] = source_url
            resp = self.session.post(url, data=data)
        elif file_path:
            with open(file_path, "rb") as f:
                resp = self.session.post(url, data=data, files={"file": f})
        else:
            raise ValueError("Must provide either source_url or file_path")
        
        resp.raise_for_status()
        return resp.json()

    def get_status(self, job_id: str) -> Dict[str, Any]:
        """
        Check the status of a running transcription job.
        """
        url = f"{self.base_url}/transcriptions/{job_id}"
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp.json()

    def get_result_raw(self, job_id: str) -> Dict[str, Any]:
        """
        Get the raw transcription result object for a COMPLETED job.
        """
        url = f"{self.base_url}/transcriptions/{job_id}/result/raw"
        resp = self.session.get(url)
        resp.raise_for_status()
        return resp.json()

    def wait_for_completion(self, job_id: str, poll_interval: int = 5, timeout: int = 600) -> Dict[str, Any]:
        """
        Poll the API until the job completes or fails, returning the result JSON.
        """
        start_time = time.time()
        while time.time() - start_time < timeout:
            status = self.get_status(job_id)
            if status["status"] == "COMPLETED":
                return self.get_result_raw(job_id)
            elif status["status"] == "FAILED":
                raise RuntimeError(f"Job failed: {status.get('error_code')} - {status.get('error_message')}")
            
            time.sleep(poll_interval)
            
        raise TimeoutError(f"Job {job_id} did not complete within {timeout} seconds.")
