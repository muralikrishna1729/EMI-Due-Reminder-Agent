import unittest
from app.history_buffer import HistoryBuffer
from app.engine import recover_pre_roll, get_utterance_buffer
from app.core import clear_utterance_buffer, _history_buffers

class TestPreRoll(unittest.TestCase):
    def setUp(self):
        # Reset the utterance buffer for this session
        clear_utterance_buffer("test_session")
        # Use a smaller duration for testing (200 ms = 4800 frames)
        self.buffer = HistoryBuffer(duration_ms=200, sample_rate=24000)
        # Store the buffer in _history_buffers so get_history_buffer returns it
        from app.core import _history_buffers
        _history_buffers["test_session"] = self.buffer

    def tearDown(self):
        # Ensure utterance buffer is cleared after each test
        clear_utterance_buffer("test_session")
        # Remove the buffer from _history_buffers to avoid conflicts with other tests
        from app.core import _history_buffers
        _history_buffers.pop("test_session", None)

    def test_recover_pre_roll_simple(self):
        # Fill buffer with frames 0..999 (1000 frames), each frame 2 bytes (1 sample)
        for i in range(1000):
            sample_val = i.to_bytes(2, 'little')
            self.buffer.add_frame(bytes(sample_val))

        print(f"Before recover: _oldest_frame_idx={self.buffer._oldest_frame_idx}, _next_frame_idx={self.buffer._next_frame_idx}, _size={self.buffer._size}")

        # Recover frames 500..600 (100 frames)
        recover_pre_roll("test_session", 500, 600)

        print(f"After recover: _oldest_frame_idx={self.buffer._oldest_frame_idx}, _next_frame_idx={self.buffer._next_frame_idx}, _size={self.buffer._size}")

        # Check that utterance buffer has 100 frames (2 bytes each)
        utterance_buf = get_utterance_buffer("test_session")
        self.assertEqual(len(utterance_buf), 100)
        # Verify content matches expected frames
        for i in range(100):
            frame_bytes = utterance_buf[i]
            expected_val = (500 + i).to_bytes(2, 'little')
            self.assertEqual(frame_bytes, expected_val)

    def test_recover_pre_roll_wraparound(self):
        # Fill buffer beyond capacity to trigger wraparound
        # Add enough frames to fill the buffer (capacity = 4800 frames)
        for i in range(self.buffer.total_samples):
            sample_val = i.to_bytes(2, 'little')
            self.buffer.add_frame(bytes(sample_val))
        # Add one extra frame to cause oldest_frame_idx to move (trigger wraparound logic)
        extra_frame = (self.buffer.total_samples).to_bytes(2, 'little')
        self.buffer.add_frame(extra_frame)

        print(f"buffer.total_samples: {self.buffer.total_samples}")
        print(f"start_idx: {self.buffer.total_samples - 100}")
        print(f"end_idx: {self.buffer.total_samples}")

        # Recover a range that wraps around: from near end to start (e.g., 4700..4800 and 0..100)
        start_idx = self.buffer.total_samples - 100  # 4700
        end_idx = self.buffer.total_samples          # 4800
        recover_pre_roll("test_session", start_idx, end_idx)

        # Check that utterance buffer has 100 frames (100 from end due to wraparound)
        utterance_buf = get_utterance_buffer("test_session")
        self.assertEqual(len(utterance_buf), 100)