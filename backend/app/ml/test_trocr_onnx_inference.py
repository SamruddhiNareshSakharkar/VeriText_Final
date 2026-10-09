import os
import sys
import time
from pathlib import Path
import numpy as np
from PIL import Image

try:
    import onnxruntime as ort
    from transformers import AutoTokenizer
except ImportError as e:
    print(f"Missing dependency: {e}")
    sys.exit(1)

WEIGHTS_DIR = Path(__file__).resolve().parent / "weights" / "trocr"

class TrOCRONNXRunner:
    def __init__(self, weights_dir: Path = WEIGHTS_DIR):
        self.weights_dir = weights_dir
        self.tokenizer = None
        self.encoder_session = None
        self.decoder_session = None
        self.decoder_type = "merged"
        self._load()

    def _load(self):
        print(f"Loading Tokenizer from {self.weights_dir}...")
        self.tokenizer = AutoTokenizer.from_pretrained(str(self.weights_dir))
        
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 4
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        enc_path = self.weights_dir / "encoder_model_quantized.onnx"
        if not enc_path.exists():
            enc_path = self.weights_dir / "encoder_model.onnx"
        
        print(f"Loading Encoder Session: {enc_path.name}...")
        self.encoder_session = ort.InferenceSession(str(enc_path), sess_options=opts, providers=["CPUExecutionProvider"])

        dec_path = self.weights_dir / "decoder_model_merged_quantized.onnx"
        if dec_path.exists() and dec_path.stat().st_size > 200 * 1024 * 1024:
            self.decoder_type = "merged"
        elif (self.weights_dir / "decoder_model_quantized.onnx").exists():
            dec_path = self.weights_dir / "decoder_model_quantized.onnx"
            self.decoder_type = "standard"
        else:
            dec_path = self.weights_dir / "decoder_model_merged.onnx"
            self.decoder_type = "merged"

        print(f"Loading Decoder Session ({self.decoder_type}): {dec_path.name}...")
        self.decoder_session = ort.InferenceSession(str(dec_path), sess_options=opts, providers=["CPUExecutionProvider"])
        print("ONNX Models successfully loaded!")

    def preprocess_image(self, image: Image.Image) -> np.ndarray:
        """Preprocesses PIL image to TrOCR input tensor (1, 3, 384, 384) float32."""
        if image.mode != "RGB":
            image = image.convert("RGB")
        resized = image.resize((384, 384), Image.Resampling.BICUBIC)
        arr = np.array(resized, dtype=np.float32) / 255.0
        # Normalize with mean=[0.5, 0.5, 0.5], std=[0.5, 0.5, 0.5]
        norm = (arr - 0.5) / 0.5
        # Transpose from (H, W, C) to (1, C, H, W)
        chw = np.transpose(norm, (2, 0, 1))
        return np.expand_dims(chw, axis=0).astype(np.float32)

    def recognize_line(self, image: Image.Image, max_length: int = 64) -> tuple[str, float]:
        """Runs end-to-end ONNX inference on a single line crop."""
        t0 = time.perf_counter()
        pixel_values = self.preprocess_image(image)

        # 1. Vision Encoder
        enc_inputs = {self.encoder_session.get_inputs()[0].name: pixel_values}
        enc_outputs = self.encoder_session.run(None, enc_inputs)
        encoder_hidden_states = enc_outputs[0] # (1, 577, 768)

        # 2. Autoregressive Decoder
        # decoder_start_token_id for RoBERTa / TrOCR is 2 (<s>)
        # eos_token_id is 2 (</s>)
        decoder_start_token_id = 2
        eos_token_id = 2
        
        current_token_ids = [decoder_start_token_id]
        log_probs = []

        dec_inputs_info = {inp.name: inp for inp in self.decoder_session.get_inputs()}
        has_use_cache = "use_cache_branch" in dec_inputs_info

        # Check if dummy past key values are required
        past_inputs = {}
        for inp_name, inp_info in dec_inputs_info.items():
            if inp_name.startswith("past_key_values"):
                # Determine shape, e.g., (1, 12, 0, 64)
                # Typically (batch, num_heads, seq_len=0, head_dim=64)
                shape = [1 if isinstance(dim, str) or dim is None else dim for dim in inp_info.shape]
                # set seq_len dimension to 0
                for idx, dim in enumerate(shape):
                    if idx == 2:
                        shape[idx] = 0
                past_inputs[inp_name] = np.zeros(shape, dtype=np.float32)

        for step in range(max_length):
            input_ids_tensor = np.array([current_token_ids], dtype=np.int64)
            
            feed = {
                "input_ids": input_ids_tensor,
                "encoder_hidden_states": encoder_hidden_states,
            }
            if has_use_cache:
                feed["use_cache_branch"] = np.array([False], dtype=bool)
                feed.update(past_inputs)

            dec_outputs = self.decoder_session.run(None, feed)
            logits = dec_outputs[0] # (1, seq_len, vocab_size)
            
            # Extract logits for last token
            last_logits = logits[0, -1, :] # (vocab_size,)
            
            # Greedy next token selection
            next_token_id = int(np.argmax(last_logits))
            
            # Compute log softmax probability
            exp_logits = np.exp(last_logits - np.max(last_logits))
            prob = exp_logits[next_token_id] / np.sum(exp_logits)
            log_prob = float(np.log(max(prob, 1e-6)))
            log_probs.append(log_prob)

            if next_token_id == eos_token_id:
                break
            
            current_token_ids.append(next_token_id)
            
            # Check for repetition loops (e.g. 5 identical tokens in a row)
            if len(current_token_ids) >= 5 and len(set(current_token_ids[-5:])) == 1:
                break

        # Decode generated token IDs
        output_tokens = current_token_ids[1:] # skip start token
        decoded_text = self.tokenizer.decode(output_tokens, skip_special_tokens=True).strip()
        
        # Calculate sequence confidence score (geometric mean of token probabilities)
        mean_log_prob = float(np.mean(log_probs)) if log_probs else -1.0
        conf_score = round(float(np.clip(np.exp(mean_log_prob), 0.05, 0.99)), 3)
        
        elapsed = round(time.perf_counter() - t0, 3)
        print(f"Recognized: '{decoded_text}' (conf: {conf_score}, time: {elapsed}s)")
        return decoded_text, conf_score

if __name__ == "__main__":
    print("Testing TrOCRONNXRunner...")
    runner = TrOCRONNXRunner()
    # Test on a dummy or test image
    test_img = Image.new("RGB", (300, 60), color=(255, 255, 255))
    text, conf = runner.recognize_line(test_img)
    print("Runner initialized and functional!")
