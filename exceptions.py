from __future__ import annotations


class TranscriptionPipelineError(Exception):
    """Base exception for all expected transcription pipeline errors."""
    error_code: str = "TRANSCRIPTION_ERROR"
    suggested_action: str = "Verify the source input and AI pipeline configuration."

    def __init__(self, message: str, error_code: str | None = None, suggested_action: str | None = None):
        super().__init__(message)
        if error_code is not None:
            self.error_code = error_code
        if suggested_action is not None:
            self.suggested_action = suggested_action


class UpstreamRateLimitError(TranscriptionPipelineError):
    """Raised when Gemini or Chirp returns a 429 Too Many Requests."""
    error_code = "UPSTREAM_RATE_LIMIT"
    suggested_action = "Job will be automatically retried after a backoff period."


class UpstreamUnavailableError(TranscriptionPipelineError):
    """Raised when Gemini or Chirp is temporarily unavailable or times out."""
    error_code = "UPSTREAM_UNAVAILABLE"
    suggested_action = "Job will be automatically retried. If the issue persists, check service health."


class MediaDownloadError(TranscriptionPipelineError):
    """Raised when the source URL cannot be downloaded."""
    error_code = "MEDIA_DOWNLOAD_FAILED"
    suggested_action = "Ensure the source URL is public, reachable, and points directly to a valid media file."


class MediaFormatError(TranscriptionPipelineError):
    """Raised when ffmpeg fails to extract or process the media file."""
    error_code = "MEDIA_INVALID_FORMAT"
    suggested_action = "Check if the file is corrupted or in an unsupported format."


class TranscriptionInternalError(TranscriptionPipelineError):
    """Raised for unexpected bugs or JSON decoding errors within the pipeline."""
    error_code = "TRANSCRIPTION_INTERNAL_ERROR"
    suggested_action = "Inspect the worker logs for detailed debugging information."
