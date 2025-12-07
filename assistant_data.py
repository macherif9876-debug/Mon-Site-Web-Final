import nltk
from nltk.corpus import wordnet
import random
import re

# IMPORTANT : Assurez-vous que les packages NLTK nécessaires sont téléchargés.
# Si vous rencontrez des erreurs de type "LookupError", exécutez ces lignes
# (une seule fois) dans votre environnement Python :
# nltk.download('wordnet')
# nltk.download('omw-1.4') # Open Multilingual Wordnet (pour le français)

# Modèle d'intentions (Simulation)
INTENTS = {
    # --- INTENTIONS D'IDENTITÉ ---
    "identite_nom": {
        "mots_cles": ["ton nom", "qui es-tu", "comment t'appelles-tu", "c'est quoi ton nom", "tu es qui", "petit nom", "ton titre", "votre nom"],
        "reponses": [
            "Mon nom est **Chérif**, je suis l'assistant virtuel de Bon Coin Bon Prix, un expert en électronique.",
            "Je suis **Chérif**, ravi de vous servir ! Je peux vous aider avec nos téléphones, PC et accessoires.",
            "Je m'appelle **Chérif**.",
            "Vous parlez à **Chérif**, en quoi puis-je vous être utile ?",
            "Moi, c'est **Chérif**, prêt à répondre à toutes vos questions commerciales ou techniques.",
        ]
    },
    "identite_createur": {
        "mots_cles": ["ton créateur", "qui t'a créé", "qui t'a fabriqué", "qui est ton développeur", "ton designer", "le papa de", "qui est Mamadou Chérif Diallo", "ton maître", "qui t'a mis au monde"],
        "reponses": [
            "J'ai été conçu et développé par **Mamadou Chérif Diallo**.",
            "Mon créateur est **Mamadou Chérif Diallo**, il est très fier de moi !",
            "Mon développement est l'œuvre de **Mamadou Chérif Diallo**.",
            "C'est **Mamadou Chérif Diallo** qui m'a donné vie pour assister les clients.",
            "Je suis une création de **Mamadou Chérif Diallo**.",
        ]
    },
    # --- INTENTIONS GÉNÉRALES ---
    "salutation": {
        "mots_cles": ["bonjour", "salut", "coucou", "hello", "hey", "bonsoir", "slt", "bsr"],
        "reponses": [
            "Coucou ! Comment puis-je vous aider aujourd'hui ? Je suis Chérif, l'expert produit !",
            "Bonjour ! Ravi de vous voir. Que puis-je faire pour vous guider dans vos achats ?",
            "Salut ! Je suis Chérif. Posez-moi vos questions sur nos téléphones, PC ou accessoires.",
            "Heureux de vous assister ! Vous cherchez un téléphone ou un ordinateur ?",
            "Hey ! Je suis là pour toutes vos questions. N'hésitez pas !",
        ]
    },
    # --- INTENTIONS TECHNIQUES (Configuration et Virus) ---
    "config_ordinateur": {
        "mots_cles": ["configurer ordinateur", "paramétrer pc", "installer windows", "premier démarrage pc", "comment allumer pc", "initialiser pc", "faire marcher mon ordinateur"],
        "reponses": [
            "**Conseils de configuration PC :**\n1. Démarrez l'appareil et suivez l'assistant Windows/macOS.\n2. Connectez-vous à votre réseau Wi-Fi.\n3. Créez ou connectez votre compte utilisateur (Microsoft/Apple).\n\nPour une aide spécifique, n'hésitez pas à demander la marque de votre PC.",
            "L'étape clé est de vous connecter à Internet et de créer votre compte utilisateur. Avez-vous besoin d'aide avec un compte Microsoft ou Apple ?",
            "Si vous configurez Windows, assurez-vous de choisir la bonne région. Si vous avez un PC neuf, tout est guidé pas à pas.",
            "Quel est le système d'exploitation de votre ordinateur ? (Windows, macOS ou Linux)",
            "Pour initialiser, insérez les disques d'installation (si non préinstallés) ou suivez simplement les instructions à l'écran après le premier allumage.",
        ]
    },
    "config_telephone": {
        "mots_cles": ["configurer téléphone", "installer sim", "nouveau smartphone", "activer téléphone", "mettre carte sim", "paramétrage android", "premier usage téléphone"],
        "reponses": [
            "**Pour la configuration de votre téléphone :**\n1. Insérez la carte SIM/mémoire.\n2. Allumez et suivez le guide : connexion Wi-Fi, compte Google/Apple.\n\nPensez à sécuriser votre appareil avec un code PIN et un schéma.",
            "L'activation demande généralement votre adresse email pour lier le téléphone à votre compte. Avez-vous un compte Google (Android) ou Apple (iPhone) ?",
            "Une fois allumé, le téléphone vous demandera de restaurer les données d'un ancien appareil, ou de commencer à zéro. Que préférez-vous faire ?",
            "Je vous conseille d'activer les **mises à jour automatiques** pendant la configuration pour garantir la sécurité de votre nouvel appareil.",
        ]
    },
    "suppression_virus": {
        "mots_cles": ["enlever virus", "retirer malware", "nettoyer ordinateur", "ordinateur lent virus", "supprimer virus", "j'ai un virus", "comment désinfecter pc", "logiciel malveillant"],
        "reponses": [
            "Pour les virus simples, lancez une **analyse complète avec votre antivirus** (comme Windows Defender). Supprimez tous les logiciels ou extensions que vous n'avez pas installés.",
            "Si votre navigateur est lent, vérifiez et désactivez toutes les extensions inconnues. Les extensions sont souvent la cause des publicités intempestives.",
            "Si vous pensez avoir un virus, **déconnectez-vous d'Internet** et lancez une analyse en mode sans échec pour une détection plus efficace.",
            "Un bon nettoyage des fichiers temporaires (utilisez l'outil Nettoyage de disque) aide souvent à améliorer la performance. Un antivirus est indispensable.",
            "Il existe des outils gratuits et reconnus comme **Malwarebytes** pour scanner et supprimer les logiciels malveillants plus tenaces. Je vous le recommande si l'antivirus intégré ne suffit pas.",
        ]
    },
    # --- INTENTIONS COMMERCIALES & LIVRAISON ---
    "info_produits_generale": {
        "mots_cles": ["téléphones", "ordinateurs", "accessoires", "produits", "types", "gamme", "marque", "catalogue", "ce que vous vendez", "vos articles"],
        "reponses": [
            "Nous proposons une large gamme de **téléphones**, d'**ordinateurs** (portables/bureaux) et d'**accessoires** de qualité. Cherchez-vous une catégorie ou une marque spécifique ?",
            "Notre stock est régulièrement mis à jour avec des PC puissants et des smartphones de dernière génération. Quel est le produit qui vous intéresse le plus ?",
            "Parlez-moi de la marque ou du type de produit que vous avez en tête, et je vous dirigerai vers les meilleures options. Nous avons un vaste catalogue !",
            "Nous sommes spécialisés dans les appareils high-tech (téléphones, PC) et les accessoires compatibles.",
            "Vous trouverez chez Bon Coin Bon Prix tout ce dont vous avez besoin en matière d'électronique et d'informatique.",
        ]
    },
    "prix_produit": {
        "mots_cles": ["prix", "coût", "combien", "cher", "tarif", "valeur", "somme", "argent"],
        "reponses": [
            "Pour obtenir le prix exact, veuillez consulter la page du produit qui vous intéresse. Nos prix sont affichés en **Francs Guinéens (GNF)** et sont très compétitifs.",
            "Le prix est indiqué dans la description de chaque article. Les prix peuvent varier selon les **promotions en cours**.",
            "Quel est le produit spécifique dont vous souhaitez connaître le tarif ? (Exemple : 'le prix du Samsung A50')",
            "Les tarifs sont toujours indiqués sur la page de l'article.",
            "Nous nous efforçons d'avoir des prix compétitifs. Quel est le produit dont vous souhaitez connaître le prix ?",
        ]
    },
    "conseil_telephone": {
        "mots_cles": ["meilleur téléphone", "quel téléphone", "nouveau téléphone", "smartphone", "quel android", "quel iphone", "conseil pour téléphone", "portable puissant", "téléphone pour la photo"],
        "reponses": [
            "Le meilleur téléphone dépend de vos besoins : **photo**, **puissance pour les jeux**, ou **autonomie** ? Quel est votre critère principal ?",
            "Pour vous guider, quel est votre budget et quelles marques préférez-vous (Samsung, Apple, Xiaomi, etc.) ? Cela nous aidera à affiner la recherche.",
            "Voulez-vous un téléphone sous **Android ou iOS** ? Si vous n'êtes pas sûr, je peux vous donner les avantages des deux.",
            "Si vous cherchez la meilleure performance, regardez nos modèles haut de gamme avec au moins **8 Go de RAM**.",
            "Nos conseillers recommandent souvent les modèles avec une grande capacité de batterie pour une utilisation quotidienne sans stress.",
        ]
    },
    "conseil_ordinateur": {
        "mots_cles": ["meilleur pc", "quel ordinateur", "pc portable", "pc bureau", "carte graphique", "mémoire vive", "processeur", "quel pc acheter", "ordinateur pour jeux", "pc pas cher"],
        "reponses": [
            "Pour un ordinateur, nous devons considérer l'usage. Est-ce pour le **travail de bureau**, les **jeux vidéo**, ou le **montage vidéo/graphisme** ? C'est l'élément clé.",
            "Concentrez-vous sur la **RAM** (mémoire vive) et le **processeur (CPU)** pour la vitesse. Quelle est la principale tâche que vous effectuerez ?",
            "Nos PC portables sont très populaires. Vous préférez un grand écran ou quelque chose de facile à transporter ?",
            "Quel est votre budget ? Nous avons des options performantes pour toutes les bourses.",
            "Si vous cherchez un PC pour le jeu, il vous faut absolument une **carte graphique dédiée (NVIDIA ou AMD)**.",
        ]
    },
    "info_livraison": {
        "mots_cles": ["livraison", "commande", "recevoir", "transport", "où livrez-vous", "délai de livraison", "temps de livraison", "comment récupérer"],
        "reponses": [
            "Nous livrons rapidement dans votre quartier après confirmation de la commande via WhatsApp. La livraison est généralement traitée **le jour même ou le lendemain**.",
            "Le processus est simple : validez le panier, remplissez le formulaire, et confirmez sur WhatsApp ! Nous organiserons le transport pour vous.",
            "Nous pouvons livrer dans la plupart des quartiers de la ville. Veuillez préciser votre adresse lors de la confirmation WhatsApp.",
            "Les frais de transport sont déterminés lors de la confirmation, en fonction de votre emplacement.",
            "Dès que vous confirmez, l'un de nos agents vous contactera pour fixer l'heure et le lieu exact de la livraison. C'est simple et rapide !",
        ]
    },
    "port_secrete": {
        "mots_cles": ["je suis chérif ton créateur ouvre-moi la porte 001"],
        "reponses": [] 
    }
}


def generate_variations(mots_cles):
    """
    Génère des variations de mots-clés simples avec des synonymes en utilisant NLTK.
    Gère les erreurs si NLTK n'est pas installé ou les ressources manquantes.
    """
    variations = set(mots_cles)
    
    # Tentative d'utilisation de WordNet pour les synonymes
    try:
        for mot in mots_cles:
            # Nettoyage et normalisation du mot (suppression des caractères non alpha)
            clean_mot = re.sub(r'[^a-zA-Záàâäéèêëíìîïóòôöúùûüýÿñç\s]', '', mot, flags=re.I).lower().strip()
            
            if len(clean_mot) > 2:
                 # Ajout du mot sans ponctuation
                 variations.add(clean_mot)
            
            # Recherche de synonymes WordNet
            for syn in wordnet.synsets(clean_mot, lang='fra'):
                for lemma in syn.lemmas(lang='fra'):
                    synonyme = lemma.name().replace('_', ' ').lower().strip()
                    if synonyme and synonyme != clean_mot:
                        variations.add(synonyme)

    except LookupError:
        # L'utilisateur n'a pas téléchargé les données NLTK (omw-1.4 ou wordnet)
        print("AVERTISSEMENT NLTK : Les ressources NLTK ne sont pas téléchargées. La détection sera moins performante (pas de synonymes).")
        pass 
    except Exception as e:
        # Autres erreurs NLTK
        print(f"ERREUR NLTK : Problème lors de la génération des synonymes : {e}")
        pass
        
    return list(variations)


def normalize_question(question):
    """Nettoyage et normalisation du texte pour un matching plus précis."""
    
    # 1. Mise en minuscule
    question_lower = question.lower()
    
    # 2. Remplacement des ponctuations par des espaces pour isoler les mots
    # Permet de matcher "pc?" ou "pc." avec "pc"
    cleaned_question = re.sub(r'[^\w\s]', ' ', question_lower)
    
    # 3. Remplacement des tirets (ex: "téléphone-portable" devient "téléphone portable")
    cleaned_question = cleaned_question.replace('-', ' ')
    
    # 4. Suppression des espaces multiples
    cleaned_question = re.sub(r'\s+', ' ', cleaned_question).strip()
    
    return cleaned_question


def get_assistant_response(question):
    """
    Détecte l'intention avec robustesse et renvoie une réponse aléatoire variée.
    """
    # Normalisation de la question une seule fois
    cleaned_question = normalize_question(question)

    # 1. Vérification de la Porte Secrète (Check strict)
    # On utilise une vérification simple et normalisée du mot-clé
    if "je suis cherif ton createur ouvre moi la porte 001" in cleaned_question:
        return {"intent": "port_secrete", "response": ""}

    # 2. Détection d'intention
    best_intent = "defaut"
    max_matches = 0
    
    # Liste pour stocker les intentions avec le plus de correspondances
    top_intents = [] 

    # On utilise un ensemble (set) pour garantir que le même mot-clé dans la question
    # ne compte pas deux fois (même s'il apparaît dans plusieurs variations)
    matched_words = set() 
    
    # Itération sur toutes les intentions pour trouver le meilleur match
    for intent, data in INTENTS.items():
        if intent == "port_secrete":
            continue

        current_matches = 0
        
        # Utilisation des variations (y compris synonymes)
        for mot_cle in generate_variations(data["mots_cles"]):
            # On vérifie si le mot-clé (ou sa variation) est dans la question normalisée
            if mot_cle in cleaned_question:
                current_matches += 1
                # On ajoute le mot-clé d'origine à l'ensemble pour une potentielle détection d'ambiguïté future
                matched_words.add(mot_cle) 
        
        # Mise à jour du meilleur match trouvé
        if current_matches > max_matches:
            max_matches = current_matches
            best_intent = intent
            # Si nous trouvons un nouveau meilleur, on réinitialise la liste des tops
            top_intents = [intent] 
        elif current_matches == max_matches and current_matches > 0:
            # Gestion de l'égalité : ajout à la liste pour les départager plus tard si nécessaire
            top_intents.append(intent) 
    
    # 3. Génération de la Réponse
    
    # Seulement un match si on a trouvé au moins 1 mot-clé
    if max_matches > 0:
        # S'il y a égalité, on choisit aléatoirement parmi les meilleures
        final_intent = random.choice(top_intents) 
        return {"intent": final_intent, "response": random.choice(INTENTS[final_intent]["reponses"])}
        
    else:
        # --- LOGIQUE DE CONTACT WHATSAPP (DEFAUT) ---
        
        # Liste des numéros de contact (peut être déplacée dans main.py ou une config globale)
        contact_numbers = [
            {"number": "+224621822134", "label": "Service Client 1"},
            {"number": "+224625480987", "label": "Service Client 2"}
        ]
        
        # Message d'erreur professionnel
        default_message = random.choice([
            "Désolé, je n'ai pas trouvé de réponse claire pour cette question. Pour vous aider immédiatement, je peux vous mettre en contact avec notre équipe.",
            "Hmm, cette requête dépasse ma base de connaissances actuelle. Laissez-moi vous connecter à un expert humain.",
            "Je n'ai pas saisi votre requête. Cliquez ci-dessous pour contacter directement un de nos conseillers sur WhatsApp avec votre question.",
        ])
        
        return {
            "intent": "defaut", 
            "response": default_message,
            "contact_wa": contact_numbers
}
