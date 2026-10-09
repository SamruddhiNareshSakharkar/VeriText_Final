import os
import math
from pathlib import Path
from typing import Dict, Any, List
import numpy as np
from PIL import Image

class HandwritingEngine:
    """
    Computer Vision Handwriting Stylometry Engine.
    Extracts geometric stroke characteristics, slant angles, stroke width variation,
    and baseline spacing rhythms from document images.
    Distinguishes between handwritten, printed, and digital-text documents
    with calibrated confidence scoring.
    """

    # Thresholds for classifying document type from image features
    _INK_DENSITY_RANGE_HW = (0.02, 0.45)      # Handwritten docs have moderate ink
    _STROKE_VAR_THRESHOLD_HW = 1.5              # High stroke variance = handwritten
    _HORIZONTAL_VAR_THRESHOLD_HW = 0.3          # Handwritten has irregular line spacing

    def analyze_document(self, file_path: str) -> Dict[str, Any]:
        path = Path(file_path)
        if not path.exists():
            return self._empty_result("File not found")

        suffix = path.suffix.lower()

        # If it's an image file, extract CV features directly from pixels
        if suffix in [".png", ".jpg", ".jpeg", ".bmp", ".webp"]:
            return self._process_image_cv(path)
        elif suffix == ".pdf":
            return self._process_pdf_cv(path)
        else:
            return self._process_text_proxy(path)

    def _process_pdf_cv(self, path: Path) -> Dict[str, Any]:
        import io
        # 1. Primary engine: PyMuPDF (pymupdf)
        try:
            import pymupdf
            doc = pymupdf.open(str(path))
            # First check if the PDF contains a significant digital text layer.
            # If so, this is a typed/digital PDF — NOT a handwritten document.
            total_text = ""
            for page in doc:
                total_text += (page.get_text("text") or "")
            if len(total_text.split()) >= 15:
                return self._process_text_proxy(path)

            for page in doc:
                imgs = page.get_images()
                if imgs:
                    for img_info in imgs:
                        xref = img_info[0]
                        base_img = doc.extract_image(xref)
                        if base_img and "image" in base_img:
                            with Image.open(io.BytesIO(base_img["image"])).convert("L") as img:
                                res = self._process_pil_cv(img)
                                if res.get("confidence", 0.0) > 0.0:
                                    return res
            # If no embedded images yielded features, render first page pixmap only for image-based/scanned pages
            if len(doc) > 0:
                pix = doc[0].get_pixmap(dpi=150)
                with Image.open(io.BytesIO(pix.tobytes("png"))).convert("L") as img:
                    res = self._process_pil_cv(img)
                    if res.get("confidence", 0.0) > 0.0:
                        return res
        except Exception:
            pass

        # 2. Fallback: pypdf
        try:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            total_text = ""
            for page in reader.pages:
                total_text += (page.extract_text() or "")
            if len(total_text.split()) >= 15:
                return self._process_text_proxy(path)

            for page in reader.pages:
                if hasattr(page, "images") and page.images:
                    for img_obj in page.images:
                        with Image.open(io.BytesIO(img_obj.data)).convert("L") as img:
                            res = self._process_pil_cv(img)
                            if res.get("confidence", 0.0) > 0.0:
                                return res
        except Exception:
            pass

        # 3. If digital text or non-handwritten, treat as digital text document
        return self._process_text_proxy(path)

    def compare_handwriting(self, features_a: List[float], features_b: List[float]) -> float:
        """
        Computes calibrated forensic stylometric similarity between two 16-dimensional
        handwriting feature vectors.
        
        Uses weighted dimensional distance across key biometric discriminators
        (slant angle, stroke variance, line spacing rhythm, stroke width distribution,
        ink distribution) rather than naive unweighted cosine similarity in positive space.
        
        Returns a percentage score (0.0 to 100.0).
        """
        if not features_a or not features_b or len(features_a) != len(features_b) or len(features_a) != 16:
            return 0.0

        vec_a = np.array(features_a, dtype=np.float32)
        vec_b = np.array(features_b, dtype=np.float32)

        # Feature discriminator weights:
        # [0] Slant Angle: 2.5
        # [1] Stroke Variance: 2.2
        # [2] Spacing Rhythm: 1.8
        # [3] Aspect Ratio: 0.8
        # [4] Ink Density: 1.0
        # [5] Vertical Proj Std: 1.0
        # [6] Stroke Mean: 2.0
        # [7] Stroke Std: 2.0
        # [8] Spacing Std: 1.5
        # [9] Horizontal Var: 1.0
        # [10] Vertical Var: 1.0
        # [11] Center X: 0.5
        # [12] Center Y: 0.5
        # [13] Top Density: 0.8
        # [14] Bottom Density: 0.8
        # [15] Density Diff: 1.0
        weights = np.array([
            2.5, 2.2, 1.8, 0.8, 1.0, 1.0, 2.0, 2.0,
            1.5, 1.0, 1.0, 0.5, 0.5, 0.8, 0.8, 1.0
        ], dtype=np.float32)
        weights = weights / np.sum(weights)

        # Feature-wise absolute differences
        diffs = np.abs(vec_a - vec_b)
        weighted_dist = float(np.sum(weights * diffs))

        # Calibrated exponential kernel:
        # Distance = 0.00 -> 100%
        # Distance = 0.05 -> 80%
        # Distance = 0.15 -> 51%
        # Distance >= 0.35 -> <= 20%
        similarity = 100.0 * math.exp(-4.5 * weighted_dist)
        score = round(max(0.0, min(100.0, similarity)), 1)
        return score

    def _process_image_cv(self, path: Path) -> Dict[str, Any]:
        try:
            with Image.open(str(path)).convert("L") as img:
                return self._process_pil_cv(img)
        except Exception as e:
            return self._empty_result(f"CV analysis error: {str(e)}")

    def _process_pil_cv(self, img: Image.Image) -> Dict[str, Any]:
        try:
            return self._extract_cv_features(img)
        except Exception as e:
            return self._empty_result(f"CV analysis error: {str(e)}")

    def _extract_cv_features(self, img: Image.Image) -> Dict[str, Any]:
        # Resize large images while preserving aspect ratio
        img_copy = img.copy()
        img_copy.thumbnail((1200, 1200))

        arr = np.array(img_copy, dtype=np.float32)

        # 1. Adaptive threshold using Otsu-like approach (bimodal split)
        hist, _ = np.histogram(arr.flatten(), bins=256, range=(0, 256))
        total_pixels = arr.size
        
        # Simple Otsu threshold computation
        cumsum = np.cumsum(hist)
        cumsum_val = np.cumsum(hist * np.arange(256))
        total_mean = cumsum_val[-1] / total_pixels
        
        best_threshold = float(np.mean(arr))  # fallback
        best_variance = 0.0
        for t in range(10, 245):
            w0 = cumsum[t]
            w1 = total_pixels - w0
            if w0 == 0 or w1 == 0:
                continue
            mean0 = cumsum_val[t] / w0
            mean1 = (cumsum_val[-1] - cumsum_val[t]) / w1
            between_var = w0 * w1 * (mean0 - mean1) ** 2
            if between_var > best_variance:
                best_variance = between_var
                best_threshold = t
        
        threshold = best_threshold
        binary = (arr < threshold).astype(np.float32)

        # 2. Improved slant estimation using gradient direction histogram
        gy, gx = np.gradient(binary)

        # Compute gradient magnitudes and directions on ink pixels only
        magnitude = np.sqrt(gx**2 + gy**2)
        mask = magnitude > 0.1  # Only consider significant gradients
        
        if np.sum(mask) > 100:
            # Compute weighted average angle of gradients
            angles = np.arctan2(gy[mask], gx[mask])
            # Convert to degrees and compute circular mean
            angle_deg = np.degrees(angles)
            
            # Focus on stroke-level gradients (near vertical strokes indicate slant)
            # Vertical strokes are near ±90°, slanted strokes deviate
            vertical_mask = (np.abs(angle_deg) > 45) & (np.abs(angle_deg) < 135)
            if np.sum(vertical_mask) > 50:
                vertical_angles = angle_deg[vertical_mask]
                # Mean deviation from 90° indicates slant
                slant_deg = round(float(np.median(vertical_angles)) - 90.0, 1)
            else:
                # Fallback to simple gradient ratio
                slant_rad = math.atan2(
                    float(np.sum(np.abs(gy[mask]))),
                    float(np.sum(np.abs(gx[mask]))) + 1e-5
                )
                slant_deg = round(math.degrees(slant_rad) - 45.0, 1)
        else:
            slant_deg = 0.0

        # Clamp slant to reasonable range
        slant_deg = max(-30.0, min(30.0, slant_deg))

        # 3. Stroke width statistics
        horizontal_runs = []

        for row in binary[::8]:  # Sample every 8th row for better statistics
            padded = np.concatenate(
                ([0], row, [0])
            )

            changes = np.diff(padded)

            starts = np.where(changes == 1)[0]
            ends = np.where(changes == -1)[0]

            for start, end in zip(starts, ends):
                width = end - start

                if 1 < width < 100:  # Filter noise (single pixel) and page borders
                    horizontal_runs.append(width)

        if horizontal_runs:
            stroke_mean = float(np.mean(horizontal_runs))
            stroke_std = float(np.std(horizontal_runs))
            stroke_variance = float(np.var(horizontal_runs))
            stroke_median = float(np.median(horizontal_runs))
        else:
            stroke_mean = 0.0
            stroke_std = 0.0
            stroke_variance = 0.0
            stroke_median = 0.0

        stroke_variance = round(
            min(stroke_variance, 10.0),
            2
        )

        # 4. Vertical projection profile (for line detection)
        vert_proj = np.sum(binary, axis=1)

        # Smooth the projection profile to reduce noise
        kernel_size = max(3, int(arr.shape[0] * 0.01))
        if kernel_size % 2 == 0:
            kernel_size += 1
        smoothed_proj = np.convolve(vert_proj, np.ones(kernel_size) / kernel_size, mode='same')

        # Find peaks (text lines)
        peaks = np.where(
            (smoothed_proj[1:-1] > smoothed_proj[:-2]) &
            (smoothed_proj[1:-1] > smoothed_proj[2:]) &
            (smoothed_proj[1:-1] > np.max(smoothed_proj) * 0.1)  # Min peak height
        )[0] + 1

        if len(peaks) > 1:
            peak_diffs = np.diff(peaks)
            # Filter out very small gaps (noise) and very large gaps (section breaks)
            median_diff = np.median(peak_diffs)
            valid_diffs = peak_diffs[(peak_diffs > median_diff * 0.3) & (peak_diffs < median_diff * 3.0)]
            
            if len(valid_diffs) > 0:
                spacing_rhythm = float(np.mean(valid_diffs))
                spacing_std = float(np.std(valid_diffs))
                spacing_cv = spacing_std / (spacing_rhythm + 1e-8)  # Coefficient of variation
            else:
                spacing_rhythm = float(np.mean(peak_diffs))
                spacing_std = float(np.std(peak_diffs))
                spacing_cv = spacing_std / (spacing_rhythm + 1e-8)
        else:
            spacing_rhythm = 0.0
            spacing_std = 0.0
            spacing_cv = 0.0

        spacing_rhythm = round(
            min(spacing_rhythm, 100.0),
            2
        )

        # 5. Image geometry
        h, w = binary.shape

        aspect_ratio = float(
            w / max(h, 1)
        )

        # 6. Ink density
        ink_density = float(
            np.mean(binary)
        )

        # 7. Horizontal projection characteristics
        horizontal_projection = np.sum(
            binary,
            axis=1
        )

        horizontal_mean = float(
            np.mean(horizontal_projection)
        )

        horizontal_std = float(
            np.std(horizontal_projection)
        )

        horizontal_variation = (
            horizontal_std /
            (horizontal_mean + 1e-8)
        )

        # 8. Vertical projection characteristics
        vertical_projection = np.sum(
            binary,
            axis=0
        )

        vertical_mean = float(
            np.mean(vertical_projection)
        )

        vertical_std = float(
            np.std(vertical_projection)
        )

        vertical_variation = (
            vertical_std /
            (vertical_mean + 1e-8)
        )

        # 9. Center of ink
        total_ink = float(
            np.sum(binary)
        )

        if total_ink > 0:
            y_indices, x_indices = np.indices(
                binary.shape
            )

            center_x = float(
                np.sum(x_indices * binary) /
                total_ink
            ) / w

            center_y = float(
                np.sum(y_indices * binary) /
                total_ink
            ) / h
        else:
            center_x = 0.0
            center_y = 0.0

        # 10. Ink distribution
        top_half = binary[:h // 2]
        bottom_half = binary[h // 2:]

        top_density = float(
            np.mean(top_half)
        ) if top_half.size else 0.0

        bottom_density = float(
            np.mean(bottom_half)
        ) if bottom_half.size else 0.0

        density_difference = abs(
            top_density - bottom_density
        )

        # 11. Connected component analysis for handwriting classification
        # Count distinct ink regions to estimate character/stroke count
        labeled = self._simple_connected_components(binary)
        num_components = int(np.max(labeled)) if labeled.size > 0 else 0
        
        # Component size statistics (handwritten = more varied component sizes)
        component_sizes = []
        for c in range(1, min(num_components + 1, 500)):
            size = np.sum(labeled == c)
            if size > 5:  # Skip tiny noise
                component_sizes.append(size)
        
        if component_sizes:
            comp_size_cv = float(np.std(component_sizes)) / (float(np.mean(component_sizes)) + 1e-8)
        else:
            comp_size_cv = 0.0

        # 12. Handwritten vs printed/digital confidence calibration
        confidence = self._compute_handwriting_confidence(
            ink_density=ink_density,
            stroke_variance=stroke_variance,
            stroke_cv=stroke_std / (stroke_mean + 1e-8),
            horizontal_variation=horizontal_variation,
            spacing_cv=spacing_cv,
            comp_size_cv=comp_size_cv,
            num_components=num_components,
            slant_deg=slant_deg,
            h=h, w=w
        )

        # 13. Feature vector
        # ALL 16 FEATURES ARE CALCULATED FROM THE IMAGE.
        feature_vector = [
            round(
                max(-1.0, min(1.0, slant_deg / 30.0)),
                4
            ),

            round(
                min(stroke_variance / 10.0, 1.0),
                4
            ),

            round(
                min(spacing_rhythm / 100.0, 1.0),
                4
            ),

            round(
                min(aspect_ratio / 5.0, 1.0),
                4
            ),

            round(
                min(ink_density, 1.0),
                4
            ),

            round(
                min(
                    float(np.std(vert_proj)) /
                    max(h, 1),
                    1.0
                ),
                4
            ),

            round(
                min(stroke_mean / 50.0, 1.0),
                4
            ),

            round(
                min(stroke_std / 25.0, 1.0),
                4
            ),

            round(
                min(spacing_std / 50.0, 1.0),
                4
            ),

            round(
                min(horizontal_variation / 10.0, 1.0),
                4
            ),

            round(
                min(vertical_variation / 10.0, 1.0),
                4
            ),

            round(
                max(0.0, min(1.0, center_x)),
                4
            ),

            round(
                max(0.0, min(1.0, center_y)),
                4
            ),

            round(
                min(top_density, 1.0),
                4
            ),

            round(
                min(bottom_density, 1.0),
                4
            ),

            round(
                min(density_difference, 1.0),
                4
            )
        ]

        # Determine document type classification
        if confidence >= 0.65:
            doc_classification = "handwritten"
        elif confidence >= 0.35:
            doc_classification = "mixed"
        else:
            doc_classification = "printed/digital"

        return {
            "slant_angle": slant_deg,
            "stroke_variance": stroke_variance,
            "spacing_rhythm": spacing_rhythm,
            "aspect_ratio": round(aspect_ratio, 2),

            "feature_vector": feature_vector,

            "metrics": {
                "ink_density": round(
                    ink_density,
                    3
                ),

                "line_count_estimate": (
                    len(peaks)
                    if len(peaks) > 0
                    else 1
                ),

                "resolution": f"{w}x{h}",

                "stroke_mean": round(
                    stroke_mean,
                    3
                ),

                "stroke_std": round(
                    stroke_std,
                    3
                ),

                "stroke_median": round(
                    stroke_median,
                    3
                ),

                "spacing_cv": round(
                    spacing_cv,
                    3
                ),

                "horizontal_variation": round(
                    horizontal_variation,
                    3
                ),

                "vertical_variation": round(
                    vertical_variation,
                    3
                ),

                "center_x": round(
                    center_x,
                    4
                ),

                "center_y": round(
                    center_y,
                    4
                ),

                "component_count": num_components,
                "component_size_cv": round(comp_size_cv, 3),
                "document_classification": doc_classification,

                "analysis_technique":
                    "Image-based handwriting "
                    "stylometry using Otsu thresholding, "
                    "gradient-histogram slant estimation, "
                    "stroke-width statistics, connected "
                    "component analysis, and projection profiles"
            },

            "confidence": round(confidence, 3)
        }

    def _simple_connected_components(self, binary: np.ndarray) -> np.ndarray:
        """
        Simple flood-fill connected components for binary image.
        Optimized: only processes a downsampled version for speed.
        """
        # Downsample for speed
        step = max(1, binary.shape[0] // 300)
        small = binary[::step, ::step]
        h, w = small.shape
        labeled = np.zeros_like(small, dtype=np.int32)
        current_label = 0

        for y in range(h):
            for x in range(w):
                if small[y, x] > 0 and labeled[y, x] == 0:
                    current_label += 1
                    if current_label > 500:  # Cap for performance
                        return labeled
                    # BFS flood fill
                    stack = [(y, x)]
                    while stack:
                        cy, cx = stack.pop()
                        if cy < 0 or cy >= h or cx < 0 or cx >= w:
                            continue
                        if small[cy, cx] == 0 or labeled[cy, cx] > 0:
                            continue
                        labeled[cy, cx] = current_label
                        stack.extend([(cy-1, cx), (cy+1, cx), (cy, cx-1), (cy, cx+1)])

        return labeled

    def _compute_handwriting_confidence(
        self, ink_density: float, stroke_variance: float,
        stroke_cv: float, horizontal_variation: float,
        spacing_cv: float, comp_size_cv: float,
        num_components: int, slant_deg: float,
        h: int, w: int
    ) -> float:
        """
        Computes a calibrated confidence score indicating how likely
        the document is handwritten (vs printed/digital).
        
        Returns a value between 0.0 (definitely not handwritten) and 1.0 (definitely handwritten).
        """
        score = 0.0
        total_weight = 0.0

        # Signal 1: Ink density in handwriting range (weight: 0.12)
        weight = 0.12
        total_weight += weight
        if self._INK_DENSITY_RANGE_HW[0] <= ink_density <= self._INK_DENSITY_RANGE_HW[1]:
            score += weight * 0.8
        elif ink_density < self._INK_DENSITY_RANGE_HW[0]:
            score += weight * 0.2  # Very sparse — might be light handwriting
        else:
            score += weight * 0.1  # Very dense — likely printed or filled

        # Signal 2: Stroke width variance (weight: 0.20)
        # Handwriting has HIGH stroke variance; printed text has low variance
        weight = 0.20
        total_weight += weight
        if stroke_variance >= self._STROKE_VAR_THRESHOLD_HW:
            score += weight * min(1.0, stroke_variance / 5.0)
        else:
            score += weight * (stroke_variance / self._STROKE_VAR_THRESHOLD_HW) * 0.3

        # Signal 3: Stroke width coefficient of variation (weight: 0.15)
        # Handwritten strokes vary a lot; printed characters are uniform
        weight = 0.15
        total_weight += weight
        if stroke_cv > 0.5:
            score += weight * min(1.0, stroke_cv / 1.5)
        else:
            score += weight * stroke_cv * 0.3

        # Signal 4: Horizontal projection variation (weight: 0.15)
        # Handwritten text has irregular line spacing
        weight = 0.15
        total_weight += weight
        if horizontal_variation >= self._HORIZONTAL_VAR_THRESHOLD_HW:
            score += weight * min(1.0, horizontal_variation / 2.0)
        else:
            score += weight * (horizontal_variation / self._HORIZONTAL_VAR_THRESHOLD_HW) * 0.3

        # Signal 5: Spacing rhythm coefficient of variation (weight: 0.12)
        # High CV = irregular spacing = handwritten
        weight = 0.12
        total_weight += weight
        if spacing_cv > 0.3:
            score += weight * min(1.0, spacing_cv / 0.8)
        else:
            score += weight * spacing_cv * 0.4

        # Signal 6: Component size variation (weight: 0.12)
        # Handwriting has very varied component sizes
        weight = 0.12
        total_weight += weight
        if comp_size_cv > 1.5:
            score += weight * min(1.0, comp_size_cv / 4.0)
        elif comp_size_cv > 0.5:
            score += weight * 0.4
        else:
            score += weight * 0.1

        # Signal 7: Non-zero slant (weight: 0.08)
        # Most handwriting has some slant; printed text is perfectly vertical
        weight = 0.08
        total_weight += weight
        abs_slant = abs(slant_deg)
        if 3.0 <= abs_slant <= 25.0:
            score += weight * 0.9
        elif abs_slant > 25.0:
            score += weight * 0.5  # Extreme slant is unusual
        else:
            score += weight * 0.2  # Nearly vertical could be either

        # Signal 8: Component density (weight: 0.06)
        # Reasonable number of components per pixel area
        weight = 0.06
        total_weight += weight
        area = h * w
        comp_density = num_components / max(area / 1000.0, 1.0)
        if 0.5 < comp_density < 10.0:
            score += weight * 0.7
        else:
            score += weight * 0.2

        # Normalize
        confidence = score / total_weight

        # Apply minimum: if the image has almost no ink, confidence should be very low
        if ink_density < 0.005:
            confidence = 0.0

        return round(max(0.0, min(1.0, confidence)), 3)

    def _process_text_proxy(self, path: Path) -> Dict[str, Any]:
        # For non-image text submissions, generate baseline typing/layout metrics
        return {
            "slant_angle": 0.0,
            "stroke_variance": 0.0,
            "spacing_rhythm": 0.0,
            "aspect_ratio": 1.0,
            "feature_vector": [0.0] * 16,
            "metrics": {
                "note": "Document submitted as digital typography / text format. Handwriting CV analysis applies to scanned or image submissions.",
                "format": path.suffix.lower()
            },
            "confidence": 0.0
        }

    def _empty_result(self, reason: str) -> Dict[str, Any]:
        return {
            "slant_angle": 0.0,
            "stroke_variance": 0.0,
            "spacing_rhythm": 0.0,
            "aspect_ratio": 0.0,
            "feature_vector": [0.0] * 16,
            "metrics": {"error": reason},
            "confidence": 0.0
        }

handwriting_engine = HandwritingEngine()
