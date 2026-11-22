import unittest
from app.history_buffer import HistoryBuffer

class TestHistoryBuffer(unittest.TestCase):
    def setUp(self):
        # Use a small capacity for fast tests: 200 ms at 24 kHz = 4800 samples
        self.buffer = HistoryBuffer(duration_ms=200, sample_rate=24000)

    def test_initial_state(self):
        self.assertEqual(self.buffer.total_samples, 4800)
        self.assertFalse(self.buffer._full)
        self.assertEqual(self.buffer._head, 0)
        self.assertEqual(self.buffer._size, 0)

    def test_add_frame_simple(self):
        # Add a small frame with 2 samples (4 bytes) using positive values only
        sample_bytes = (1000).to_bytes(2, 'little') + (2000).to_bytes(2, 'little')
        self.buffer.add_frame(sample_bytes)

        # Verify state after adding
        self.assertEqual(self.buffer._size, 2)
        self.assertFalse(self.buffer._full)
        self.assertEqual(self.buffer._head, 0)  # head stays same until buffer fills

    def test_add_frame_and_wraparound(self):
        # Fill buffer beyond capacity to trigger wraparound
        # Create a frame with 4800 samples (capacity) to fill the buffer
        large_samples = []
        for i in range(4800):
            large_samples.append((i * 10).to_bytes(2, 'little'))
        large_bytes = b''.join(large_samples)
        self.buffer.add_frame(large_bytes)

        # After overflow, size should equal capacity and head should have moved
        self.assertTrue(self.buffer._full)
        self.assertEqual(self.buffer._size, self.buffer.total_samples)
        # head should be (initial_head + added_samples) % capacity
        expected_head = (0 + 4800) % self.buffer.total_samples
        self.assertEqual(self.buffer._head, expected_head)

    def test_copy_range_valid(self):
        # Fill buffer with sequential samples 0..999 (each sample value = index)
        samples = bytearray()
        for i in range(1000):
            val = i.to_bytes(2, 'little')
            samples.extend(val)
        self.buffer.add_frame(bytes(samples))

        # Copy range 100..200 (100 samples)
        copied = self.buffer.copy_range(100, 200)
        self.assertEqual(len(copied), 100 * 2)  # 2 bytes per sample

        # Verify content matches expected values
        expected = bytearray()
        for i in range(100, 200):
            expected.extend(i.to_bytes(2, 'little'))
        self.assertEqual(copied, expected)

    def test_copy_range_wraparound(self):
        # Fill buffer so that it wraps around
        samples = bytearray()
        for i in range(1000):
            val = i % 32767  # stay within Int16 range
            samples.extend(val.to_bytes(2, 'little'))
        self.buffer.add_frame(bytes(samples))  # now buffer has 1000 samples, not full yet (capacity 4800)

        # Fill buffer beyond capacity to make it full
        extra = b''.join([ (i * 10).to_bytes(2, 'little') for i in range(3800) ])
        self.buffer.add_frame(extra)  # now buffer is full (size = capacity)

        # Request a range that does not wrap around: from 100 to 200 (within capacity)
        start_idx = 100
        end_idx = 200
        copied = self.buffer.copy_range(start_idx, end_idx)

        # Expected length: (end_idx - start_idx) * 2 (2 bytes per sample)
        expected_len = (end_idx - start_idx) * 2
        self.assertEqual(len(copied), expected_len)

    def test_invalid_range(self):
        with self.assertRaises(ValueError):
            self.buffer.copy_range(0, -1)
        with self.assertRaises(ValueError):
            self.buffer.copy_range(-5, 10)
        with self.assertRaises(ValueError):
            self.buffer.copy_range(10, 5)

    def test_frames_up_to(self):
        # Fill buffer partially
        for i in range(500):
            self.buffer.add_frame((i * 10).to_bytes(2, 'little'))
        # Get frames up to index 400
        frames = self.buffer.frames_up_to(400)
        self.assertEqual(len(frames), 400)
        # Verify that frames 0..399 are in order
        for i, sample_bytes in enumerate(frames):
            val = int.from_bytes(sample_bytes, 'little')
            self.assertEqual(val, i * 10)

if __name__ == '__main__':
    unittest.main()