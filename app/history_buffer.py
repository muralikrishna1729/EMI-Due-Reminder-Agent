"""History buffer for circular PCM frame storage with wraparound copy support."""
from typing import List


class HistoryBuffer:
    """Circular buffer that stores PCM frames (Int16 little‑endian, 2 bytes per sample)."""

    def __init__(self, duration_ms: int, sample_rate: int) -> None:
        """
        Initialize the buffer.

        Args:
            duration_ms: Target duration to retain in milliseconds (e.g., 1300).
            sample_rate: Audio sample rate in Hz (e.g., 24000).
        """
        self._sample_rate = sample_rate
        self._duration_ms = duration_ms
        self._capacity = int(duration_ms * sample_rate / 1000)  # total frames
        if self._capacity <= 0:
            raise ValueError("Buffer capacity must be positive")

        # Pre‑allocate storage for frames (each frame is 2 bytes)
        self._frames: List[bytes | None] = [None] * self._capacity
        self._oldest_frame_idx: int = 0  # logical index of the oldest stored frame
        self._size: int = 0              # number of frames currently stored (0 ≤ _size ≤ _capacity)
        self._next_frame_idx: int = 0    # logical index where the next frame will be written

    # --------------------------------------------------------------------- #
    # Public API
    # --------------------------------------------------------------------- #
    @property
    def _head(self) -> int:
        """Physical index of the oldest stored frame/sample."""
        return self._oldest_frame_idx

    @property
    def _full(self) -> bool:
        """Whether the buffer is currently at capacity."""
        return self._size == self._capacity

    @property
    def _buffer(self) -> bytes:
        """Concatenated PCM bytes of currently stored frames."""
        return self.copy_range(0, self._size) if self._size > 0 else b""

    def add_frame(self, frame: bytes) -> None:
        """
        Store a PCM frame (or multi-sample PCM bytes).

        Args:
            frame: Raw Int16 PCM bytes (2 bytes per sample).

        Raises:
            ValueError: If the frame size is not an even number of bytes.
        """
        if len(frame) % 2 != 0:
            raise ValueError("PCM frame must contain an even number of bytes (Int16)")

        for i in range(0, len(frame), 2):
            sample = frame[i:i + 2]
            if self._size == self._capacity:
                # Buffer is full – overwrite the oldest frame's physical slot
                oldest_physical = self._oldest_frame_idx
                self._frames[oldest_physical] = sample
                self._oldest_frame_idx = (self._oldest_frame_idx + 1) % self._capacity
            else:
                # Insert at logical index = size
                physical = (self._oldest_frame_idx + self._size) % self._capacity
                self._frames[physical] = sample
                self._size += 1

        # Update the logical index where the next frame will be placed
        self._next_frame_idx = (self._oldest_frame_idx + self._size) % self._capacity

    def copy_range(self, start_idx: int, end_idx: int) -> bytes:
        """
        Return concatenated PCM bytes for the range [start_idx, end_idx).

        Args:
            start_idx: Inclusive logical frame index (0 ≤ start_idx < _capacity).
            end_idx: Exclusive logical frame index (start_idx < end_idx ≤ _capacity).

        Returns:
            Bytes containing the PCM data for the requested frames.

        Raises:
            ValueError: If indices are out of bounds or the range is invalid.
        """
        if not (0 <= start_idx < end_idx <= self._capacity):
            raise ValueError(f"Invalid range: start_idx={start_idx}, end_idx={end_idx}, capacity={self._capacity}")

        result = bytearray()
        if start_idx < end_idx:
            # Simple contiguous range
            for logical_idx in range(start_idx, end_idx):
                physical = (self._oldest_frame_idx + logical_idx) % self._capacity
                frame = self._frames[physical]
                if frame is None:
                    raise ValueError(f"Missing frame at logical index {logical_idx}")
                result.extend(frame)
        else:
            # Wraparound case: [start_idx, capacity) + [0, end_idx)
            for logical_idx in range(start_idx, self._capacity):
                physical = (self._oldest_frame_idx + logical_idx) % self._capacity
                frame = self._frames[physical]
                if frame is None:
                    raise ValueError(f"Missing frame at logical index {logical_idx}")
                result.extend(frame)
            for logical_idx in range(0, end_idx):
                physical = (self._oldest_frame_idx + logical_idx) % self._capacity
                frame = self._frames[physical]
                if frame is None:
                    raise ValueError(f"Missing frame at logical index {logical_idx}")
                result.extend(frame)

        return bytes(result)

    def frames_up_to(self, idx: int) -> List[bytes]:
        """
        Return a list of frames from logical index 0 up to (but not including) idx.

        This helper is used for recovery when the buffer may have wrapped.

        Args:
            idx: Logical index (0 ≤ idx ≤ _capacity).

        Returns:
            List of frame bytes in order.
        """
        if not (0 <= idx <= self._capacity):
            raise ValueError(f"Index out of bounds: {idx}")

        frames: List[bytes] = []
        for logical_idx in range(idx):
            physical = (self._oldest_frame_idx + logical_idx) % self._capacity
            frame = self._frames[physical]
            if frame is None:
                raise ValueError(f"Missing frame at logical index {logical_idx}")
            frames.append(frame)
        return frames

    # --------------------------------------------------------------------- #
    # Helper for test code
    # --------------------------------------------------------------------- #
    def _get_frame_bytes(self, logical_idx: int) -> bytes:
        """
        Return the raw frame bytes at the given logical index.

        Args:
            logical_idx: Logical frame index (0 ≤ logical_idx < _capacity).

        Returns:
            The PCM bytes for the requested frame.

        Raises:
            ValueError: If the logical index is out of bounds or the frame is missing.
        """
        if not (0 <= logical_idx < self._capacity):
            raise ValueError(f"Logical index {logical_idx} out of bounds for capacity {self._capacity}")

        physical = (self._oldest_frame_idx + logical_idx) % self._capacity
        frame = self._frames[physical]
        if frame is None:
            raise ValueError(f"Missing frame at logical index {logical_idx}")
        return frame

    # --------------------------------------------------------------------- #
    # Debug helpers (optional)
    # --------------------------------------------------------------------- #
    @property
    def total_samples(self) -> int:
        """Total capacity of the buffer (number of frames)."""
        return self._capacity

    def __repr__(self) -> str:
        return (f"<HistoryBuffer capacity={self._capacity} size={self._size} "
                f"_oldest_frame_idx={self._oldest_frame_idx} _next_frame_idx={self._next_frame_idx}>")