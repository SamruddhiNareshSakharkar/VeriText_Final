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
    """

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
            # If no embedded images yielded features, render first page pixmap
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
        Computes cosine similarity between two 16-dimensional handwriting feature vectors.
        Returns a percentage score (0.0 to 100.0).
        """
        if not features_a or not features_b or len(features_a) != len(features_b):
            return 0.0

        vec_a = np.array(features_a, dtype=np.float32)
        vec_b = np.array(features_b, dtype=np.float32)

        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)

        if norm_a == 0 or norm_b == 0:
            return 0.0

        cosine = float(np.dot(vec_a, vec_b) / (norm_a * norm_b))
        score = round(max(0.0, min(100.0, (cosine * 100.0))), 1)
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

        # 1. Adaptive threshold using image mean
        threshold = float(np.mean(arr))
        binary = (arr < threshold).astype(np.float32)

        # 2. Slant estimation
        gy, gx = np.gradient(binary)

        slant_rad = math.atan2(
            float(np.sum(np.abs(gy))),
            float(np.sum(np.abs(gx))) + 1e-5
        )

        slant_deg = round(
            math.degrees(slant_rad) - 45.0,
            1
        )

        # 3. Stroke width statistics
        horizontal_runs = []

        for row in binary[::10]:
            padded = np.concatenate(
                ([0], row, [0])
            )

            changes = np.diff(padded)

            starts = np.where(changes == 1)[0]
            ends = np.where(changes == -1)[0]

            for start, end in zip(starts, ends):
                width = end - start

                if width > 0:
                    horizontal_runs.append(width)

        if horizontal_runs:
            stroke_mean = float(np.mean(horizontal_runs))
            stroke_std = float(np.std(horizontal_runs))
            stroke_variance = float(np.var(horizontal_runs))
        else:
            stroke_mean = 0.0
            stroke_std = 0.0
            stroke_variance = 0.0

        stroke_variance = round(
            min(stroke_variance, 10.0),
            2
        )

        # 4. Vertical projection profile
        vert_proj = np.sum(binary, axis=1)

        peaks = np.where(
            (vert_proj[1:-1] > vert_proj[:-2]) &
            (vert_proj[1:-1] > vert_proj[2:])
        )[0] + 1

        if len(peaks) > 1:
            peak_diffs = np.diff(peaks)

            spacing_rhythm = float(
                np.mean(peak_diffs)
            )

            spacing_std = float(
                np.std(peak_diffs)
            )
        else:
            spacing_rhythm = 0.0
            spacing_std = 0.0

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

        # 11. Feature vector
        # ALL 16 FEATURES ARE CALCULATED FROM THE IMAGE.
        feature_vector = [
            round(
                max(-1.0, min(1.0, slant_deg / 45.0)),
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

                "analysis_technique":
                    "Image-based handwriting "
                    "stylometry using thresholding, "
                    "gradient analysis, stroke-width "
                    "statistics and projection profiles"
            },

            "confidence": 0.85
        }

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
