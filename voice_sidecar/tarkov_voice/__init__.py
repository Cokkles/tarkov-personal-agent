"""Voice marker sidecar for Tarkov Personal Agent.

Listens to the microphone, transcribes speech locally with faster-whisper, scans the
transcript for callouts ("I hear something to my left", "found a keycard") and posts
timestamped markers to the local Tarkov Personal Agent API.
"""

__version__ = "0.1.0"
