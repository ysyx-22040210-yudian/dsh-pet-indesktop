"""Contracts for offline contour smoothing and fixed clip placement."""

import pytest

np = pytest.importorskip("numpy", reason="offline media processing environment")
pytest.importorskip("cv2", reason="offline media processing environment")

from scripts.repair_alpha_geometry import smooth_transform_rgba


def test_contour_gets_coverage_without_transparent_rgb_halo():
    frame = np.zeros((90, 130, 4), np.uint8)
    frame[:, :, :3] = [0, 255, 0]  # invisible chroma must not leak
    frame[15:75, 30:95] = [244, 183, 72, 255]
    for row in range(16, 70):
        frame[row, 25 + (row // 3):30] = [244, 183, 72, 255]
    original = frame.copy()

    result, _ = smooth_transform_rgba(frame, scale=1, dx=.35, dy=.4)

    np.testing.assert_array_equal(frame, original)
    np.testing.assert_array_equal(result[25:65, 40:80], original[25:65, 40:80])
    coverage = (result[:, :, 3] > 0) & (result[:, :, 3] < 255)
    assert np.count_nonzero(coverage) > 150
    visible = result[:, :, 3] >= 16
    assert np.max(abs(result[:, :, :3][visible].astype(int) - [244, 183, 72])) <= 2
    assert np.max(result[:8, :, 3]) == 0


def test_fixed_transform_preserves_motion_and_thin_features():
    first = np.zeros((120, 180, 4), np.uint8)
    first[35:95, 50:110] = [230, 170, 80, 255]
    first[20:36, 79:81] = [230, 170, 80, 255]  # thin horn
    later = np.roll(np.roll(first, 6, axis=1), -8, axis=0)

    a, _ = smooth_transform_rgba(first, scale=1.1, dx=-12.2, dy=5.1)
    b, _ = smooth_transform_rgba(later, scale=1.1, dx=-12.2, dy=5.1)

    def centroid(image):
        alpha = image[:, :, 3].astype(float)
        y, x = np.indices(alpha.shape)
        return np.array([(x * alpha).sum(), (y * alpha).sum()]) / alpha.sum()

    np.testing.assert_allclose(centroid(b) - centroid(a), [6.6, -8.8], atol=.15)
    assert a[28:39, 75:79, 3].max() > 180
    assert a[:, :, 3].sum() / first[:, :, 3].sum() == pytest.approx(1.21, rel=.015)


@pytest.mark.parametrize("scale,sigma", [(0, .65), (-1, .65), (1, -1)])
def test_invalid_transform_is_rejected(scale, sigma):
    with pytest.raises(ValueError):
        smooth_transform_rgba(np.zeros((20, 20, 4), np.uint8), scale=scale, sigma=sigma)
