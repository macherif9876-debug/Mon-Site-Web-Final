# assistant_model_persistence.py
import pickle
import os

ASSISTANT_MODEL_FILE = "assistant_data.pkl"

def save_model(pipeline):
    try:
        with open(ASSISTANT_MODEL_FILE, 'wb') as f:
            pickle.dump(pipeline, f)
        print(f"Modèle sauvegardé dans : {ASSISTANT_MODEL_FILE}")
    except Exception as e:
        print(f"ERREUR sauvegarde modèle : {e}")

def load_model():
    if not os.path.exists(ASSISTANT_MODEL_FILE):
        print(f"Fichier modèle non trouvé → entraînement nécessaire")
        return None
    try:
        with open(ASSISTANT_MODEL_FILE, 'rb') as f:
            pipeline = pickle.load(f)
        print(f"Modèle chargé avec succès : {ASSISTANT_MODEL_FILE}")
        return pipeline
    except Exception as e:
        print(f"Modèle corrompu → suppression et ré-entraînement : {e}")
        try:
            os.remove(ASSISTANT_MODEL_FILE)
        except:
            pass
        return None