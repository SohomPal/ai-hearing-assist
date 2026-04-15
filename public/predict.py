import pickle
from sentence_transformers import SentenceTransformer
import warnings

warnings.filterwarnings("ignore")

# ── LOAD MODELS ONCE ───────────────────────────────────────────
clf = pickle.load(open("intent_model.pkl", "rb"))
le = pickle.load(open("label_encoder.pkl", "rb"))
embedder = SentenceTransformer("all-MiniLM-L6-v2")


# ── MAIN FUNCTION ──────────────────────────────────────────────
def predict_intent(text: str) -> str:
    """
    Takes input text and returns predicted intent.
    """
    embedding = embedder.encode([text])
    pred = clf.predict(embedding)
    intent = le.inverse_transform(pred)[0]
    return intent
