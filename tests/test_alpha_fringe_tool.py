"""Offline media-tool contracts; these dependencies are not app dependencies."""

import pytest

np = pytest.importorskip("numpy", reason="offline media processing environment")
pytest.importorskip("cv2", reason="offline media processing environment")

from scripts.repair_alpha_fringe import repair_rgba


def test_fringe_cleanup_keeps_alpha_and_foreground_identity():
    frame = np.zeros((100, 150, 4), dtype=np.uint8)
    frame[10:90, 10:85] = [244, 183, 72, 255]
    frame[10:12, 10:85] = [93, 188, 32, 160]
    frame[12:90, 10:12] = [93, 188, 32, 255]
    frame[40:55, 85:92] = [93, 188, 32, 80]  # a fine, partially opaque strand
    original = frame.copy()

    fixed, stats = repair_rgba(frame)

    np.testing.assert_array_equal(frame, original)
    np.testing.assert_array_equal(fixed[:, :, 3], original[:, :, 3])
    np.testing.assert_array_equal(fixed[22:77, 23:72], original[22:77, 23:72])
    for row, col in [(10, 30), (50, 10), (45, 88)]:
        assert fixed[row, col, 0] > fixed[row, col, 1]
    assert stats["recolored_pixels"] > 0


def test_real_green_props_and_other_foreground_colors_are_preserved():
    frame = np.zeros((140, 240, 4), dtype=np.uint8)
    frame[20:115, 15:100] = [244, 183, 72, 255]
    frame[45:95, 130:180] = [35, 175, 60, 255]  # genuine green prop
    frame[30:45, 190:205] = [210, 35, 35, 255]
    frame[60:75, 190:205] = [35, 70, 210, 255]
    frame[90:105, 190:205] = [248, 248, 248, 255]

    fixed, stats = repair_rgba(frame)

    opaque = frame[:, :, 3] == 255
    np.testing.assert_array_equal(fixed[opaque], frame[opaque])
    assert stats["protected_green_pixels"] > 0
