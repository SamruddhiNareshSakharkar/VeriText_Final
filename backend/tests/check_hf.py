from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

m_name = "Hello-SimpleAI/chatgpt-detector-roberta"
tok = AutoTokenizer.from_pretrained(m_name)
mod = AutoModelForSequenceClassification.from_pretrained(m_name)
print("Config id2label:", mod.config.id2label)

s_human = "We started the experiment at dawn. Rain was pounding against the lab windows, making it hard to hear the spectrometer calibrate. But Dr. Vance didn't care at all. He just kept pouring the saline. Why did the temperature drop so suddenly? Nobody had an answer. By noon, however, the precipitation had stopped, and our readings stabilized."

inputs = tok(s_human, return_tensors="pt", truncation=True, max_length=512)
with torch.no_grad():
    out = mod(**inputs)
    probs = torch.softmax(out.logits, dim=-1)[0].tolist()
print("Human sample probs:", probs)
