// --- Configuration ---

// ✅ Panier : Structure Object pour un accès rapide par ID
let cart = JSON.parse(localStorage.getItem('cart')) || {};

// --- FONCTIONS UTILITAIRES GLOBALES POUR LE PANIER ---

/** Calcule le nombre total d'articles (pour le badge du panier) */
function getTotalItemCount() {
    let count = 0;
    for (const productId in cart) {
        count += cart[productId].quantity;
    }
    return count;
}

/** Met à jour le petit chiffre sur l'icône du panier */
function updateCartIconCount() {
    const cartIcon = document.getElementById('cart-count');
    const totalCount = getTotalItemCount();

    if (cartIcon) {
        if (totalCount > 0) {
            cartIcon.textContent = totalCount;
            cartIcon.style.display = 'inline-block';
        } else {
            cartIcon.style.display = 'none';
        }
    }
}

/** Formatage d'un prix en GNF */
function formatGNF(amount) {
    const num = parseFloat(amount);
    if (isNaN(num)) return '0 GNF';
    // Utilise Intl.NumberFormat pour un bon formatage des grands nombres
    return new Intl.NumberFormat('fr-FR', {
        style: 'currency',
        currency: 'GNF',
        minimumFractionDigits: 0
    }).format(num);
}

/** Met à jour le localStorage et l'interface utilisateur */
function updateCart() {
    const cleanCart = Object.fromEntries(
        Object.entries(cart).filter(([key, item]) => item.quantity > 0)
    );
    cart = cleanCart;

    localStorage.setItem('cart', JSON.stringify(cart));

    if (document.querySelector('.cart-container')) {
        renderCart();
    }
    updateCartIconCount();
}

/** Ajuste la quantité d'un produit dans le panier (Boutons +/-) */
window.updateQuantity = function(id, delta) {
    if (cart[id]) {
        cart[id].quantity += delta;

        if (cart[id].quantity <= 0) {
            delete cart[id];
        }
        updateCart();
    }
};

/** Supprime un produit du panier */
window.removeItem = function(id) {
    if (confirm("Voulez-vous vraiment supprimer cet article de votre panier ?")) {
        delete cart[id];
        updateCart();
    }
};

/** Rend l'affichage complet du panier (Calcul des totaux) */
function renderCart() {
    const listContainer = document.getElementById('cart-items-list');
    const totalAmountElement = document.getElementById('cart-total-amount');
    const checkoutSection = document.getElementById('cart-checkout-section');
    const emptyMessage = document.getElementById('empty-cart-message');
    const checkoutFormContainer = document.getElementById('checkout-form-container');
    const showCheckoutBtn = document.getElementById('show-checkout-btn');

    listContainer.innerHTML = '';
    let grandTotal = 0;
    let itemCount = 0;

    for (const productId in cart) {
        const item = cart[productId];
        const price = parseFloat(item.prix);
        const subtotal = price * item.quantity;
        grandTotal += subtotal;
        itemCount++;

        const itemHTML = `
            <div class="cart-item-detail">
                <div class="item-info">
                    <span class="item-name">${item.nom}</span>
                    <span class="item-unit-price-small">${formatGNF(price)} / unité</span>
                </div>

                <div class="item-controls-group">
                    <div class="quantity-controls">
                        <button class="btn btn-sm btn-minus" onclick="updateQuantity('${item.id}', -1)">-</button>
                        <span class="item-quantity-display">${item.quantity}</span>
                        <button class="btn btn-sm btn-plus" onclick="updateQuantity('${item.id}', 1)">+</button>
                    </div>

                    <span class="item-subtotal-large">${formatGNF(subtotal)}</span>
                    <button class="btn btn-sm btn-remove" onclick="removeItem('${item.id}')">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
            <hr class="item-separator">
        `;
        listContainer.innerHTML += itemHTML;
    }

    if (itemCount > 0) {
        checkoutSection.style.display = 'block';
        emptyMessage.style.display = 'none';
        totalAmountElement.textContent = formatGNF(grandTotal);
        // Affiche le bouton si le formulaire n'est pas déjà ouvert
        if (checkoutFormContainer.style.display !== 'block') {
             showCheckoutBtn.style.display = 'block';
        }
    } else {
        checkoutSection.style.display = 'none';
        emptyMessage.style.display = 'block';
        checkoutFormContainer.style.display = 'none';
    }
}

/** Gère l'ajout d'un produit depuis un bouton */
window.addToCart = function(id, nom, prix) {
    const priceFloat = parseFloat(prix);
    const productId = id.toString();

    if (cart[productId]) {
        cart[productId].quantity += 1;
    } else {
        cart[productId] = {
            id: productId,
            nom: nom,
            prix: priceFloat,
            quantity: 1
        };
    }

    updateCart();
    alert(`"${nom}" ajouté au panier !`);
};

// --- LOGIQUE DE COMMANDE WHATSAPP ET ENREGISTREMENT ADMIN ---

/** Récupère le numéro WhatsApp principal de la variable globale */
function getPrimaryWhatsappNumber() {
    // Lis la variable globale définie dans base.html
    return window.PRIMARY_WHATSAPP_NUMBER || null;
}

/** Construit le message WhatsApp */
function buildWhatsappMessage(clientName, clientQuartier, grandTotal) {
    let message = `*COMMANDE EN LIGNE BON COIN BON PRIX*\n\n`;
    message += `👤 Client: ${clientName}\n`;
    message += `📍 Quartier/Ville: ${clientQuartier}\n\n`;
    message += `--- DÉTAILS DE LA COMMANDE ---\n`;

    for (const productId in cart) {
        const item = cart[productId];
        const price = parseFloat(item.prix);
        const subtotal = price * item.quantity;
        message += `* ${item.quantity}x ${item.nom} (Prix Unitaire: ${formatGNF(price)}, Sous-total: ${formatGNF(subtotal)})\n`;
    }

    message += `\n*MONTANT TOTAL À PAYER: ${formatGNF(grandTotal)}*`;
    message += `\n\nMerci de confirmer la disponibilité et la livraison.`;

    return encodeURIComponent(message);
}

// --- NOUVELLE FONCTION : Enregistrer la commande sur l'API (pour l'Administration) ---
/**
 * Enregistre la commande via une API.
 * @param {string} clientName
 * @param {string} clientQuartier
 * @param {number} grandTotal
 * @returns {Promise<boolean>} True si l'enregistrement a réussi, False sinon.
 */
async function recordOrderOnAPI(clientName, clientQuartier, grandTotal) {
    const orderData = {
        clientName: clientName,
        clientQuartier: clientQuartier,
        grandTotal: grandTotal,
        // Enregistrement des produits commandés pour l'administration
        items: Object.values(cart).map(item => ({
            id: item.id,
            nom: item.nom,
            prix: parseFloat(item.prix),
            quantity: item.quantity
        }))
    };

    try {
        // NOTE: L'URL '/api/enregistrer-commande' doit exister sur votre serveur
        const response = await fetch('/api/enregistrer-commande', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(orderData)
        });

        if (!response.ok) {
            // Log l'erreur mais ne bloque pas totalement l'utilisateur (on essaie quand même WA)
            console.error(`Erreur serveur lors de l'enregistrement de la commande: ${response.statusText}`);
            return false;
        }

        // Succès de l'enregistrement dans l'administration
        return true;
    } catch (error) {
        console.error("Erreur de connexion API pour l'enregistrement de la commande:", error);
        return false;
    }
}


// --- SYNTHÈSE VOCALE (TTS) ---

const synth = window.speechSynthesis;

/**
 * Lit le texte à haute voix en français.
 * @param {string} text Le texte à lire.
 */
function speak(text) {
    // Arrêter la parole précédente pour ne pas les superposer
    if (synth.speaking) {
        synth.cancel();
    }

    // Vérifier si le haut-parleur est actif
    if (!window.SPEAKER_ACTIVE) {
        return;
    }

    // Retirer les balises HTML et Markdown pour la lecture
    const cleanText = text.replace(/<(?:.|\n)*?>/gm, '').replace(/\*\*/g, '');

    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.lang = 'fr-FR';

    // Trouver une voix française si possible
    const frenchVoice = synth.getVoices().find(voice => voice.lang === 'fr-FR' || voice.lang === 'fr_FR');
    if (frenchVoice) {
        utterance.voice = frenchVoice;
    }

    synth.speak(utterance);
}

/**
 * Met à jour l'état du haut-parleur (actif/inactif).
 * @param {boolean} isActive Nouvel état.
 */
function setSpeakerState(isActive) {
    window.SPEAKER_ACTIVE = isActive;
    localStorage.setItem('speakerActive', isActive);

    // Mettre à jour tous les boutons haut-parleur visibles
    document.querySelectorAll('.speaker-icon').forEach(icon => {
        if (isActive) {
            icon.classList.add('active');
            icon.textContent = '🔊';
        } else {
            icon.classList.remove('active');
            icon.textContent = '🔇';
        }
    });

    if (!isActive && synth.speaking) {
        synth.cancel(); // Arrêter la lecture si on désactive
    }
}


document.addEventListener('DOMContentLoaded', () => {

    updateCartIconCount();

    // --- Variables existantes ---
    const body = document.body;
    const themeToggle = document.getElementById('theme-toggle');
    const showCheckoutBtn = document.getElementById('show-checkout-btn');
    const checkoutFormContainer = document.getElementById('checkout-form-container');
    const checkoutForm = document.getElementById('checkout-form');

    // --- Variables de l'Assistant Chérif (pour ne pas les toucher) ---
    const assistantContainer = document.querySelector('.assistant-container');
    const toggleCherifBtn = document.getElementById('toggle-cherif');
    const cherifWindow = document.getElementById('cherif-window');
    const assistantChatbox = document.getElementById('assistant-chatbox');
    const assistantInput = document.getElementById('assistant-input');
    const sendButton = document.getElementById('assistant-send-btn');
    const micButton = document.getElementById('mic-toggle');

    // --- Stocke la dernière question posée par l'utilisateur ---
    let lastUserQuestion = "";


    // --- 1. Gestion du Menu Hamburger (EXISTANT) ---
    const mainMenuToggle = document.getElementById('toggle-menu');
    const mainMenu = document.getElementById('main-menu');
    if (mainMenuToggle && mainMenu) {
        mainMenuToggle.addEventListener('click', () => {
            mainMenu.classList.toggle('is-active');
        });
    }

    // --- 2. Logique du Thème (EXISTANT) ---
    if (themeToggle) {
        const currentTheme = localStorage.getItem('theme') || 'light-mode';
        body.className = currentTheme;
        themeToggle.textContent = currentTheme === 'light-mode' ? '🌙' : '☀️';

        themeToggle.addEventListener('click', () => {
            if (body.classList.contains('light-mode')) {
                body.classList.replace('light-mode', 'dark-mode');
                localStorage.setItem('theme', 'dark-mode');
                themeToggle.textContent = '☀️';
            } else {
                body.classList.replace('dark-mode', 'light-mode');
                localStorage.setItem('theme', 'light-mode');
                themeToggle.textContent = '🌙';
            }
        });
    }

    // --- 3. Logique de l'Assistant Chérif (CODE ORIGINAL INTACT) ---

    /**
     * Ajoute un message à la chatbox.
     * @param {string} text Le texte du message.
     * @param {string} sender Le destinataire ('user' ou 'assistant').
     * @returns {HTMLElement} L'élément de texte du message.
     */
    function appendMessage(text, sender) {
        const messageContainer = document.createElement('div');
        messageContainer.classList.add('chat-message', sender);

        const avatar = document.createElement('span');
        avatar.textContent = (sender === 'assistant' ? '🤖 ' : '');

        const messageText = document.createElement('span');
        messageText.innerHTML = text;

        messageContainer.appendChild(avatar);

        // NOUVEAU : Ajout du bouton haut-parleur pour les réponses de l'assistant
        if (sender === 'assistant') {
            const speakerIcon = document.createElement('button');
            speakerIcon.classList.add('speaker-icon');
            speakerIcon.title = "Lire à haute voix";
            speakerIcon.textContent = window.SPEAKER_ACTIVE ? '🔊' : '🔇';
            if (window.SPEAKER_ACTIVE) {
                speakerIcon.classList.add('active');
            }

            // Logique de basculement du haut-parleur
            speakerIcon.addEventListener('click', function(e) {
                e.stopPropagation(); // Évite les interférences
                const isActive = speakerIcon.classList.toggle('active');
                setSpeakerState(isActive);

                if (isActive) {
                    // Si on active, on relance la lecture du message
                    speak(messageText.innerHTML);
                } else {
                    // Si on désactive, on arrête toute lecture en cours
                    synth.cancel();
                }
            });

            // Placer le haut-parleur au début (avant le texte)
            messageContainer.appendChild(speakerIcon);
        }

        messageContainer.appendChild(messageText);

        assistantChatbox.appendChild(messageContainer);
        assistantChatbox.scrollTop = assistantChatbox.scrollHeight;

        return messageText; // On retourne l'élément de texte
    }

    // Fonction améliorée pour la frappe progressive et le formatage
    function typeResponse(text, targetElement) {
        return new Promise(resolve => {
            // Convertir le format Markdown simple en HTML
            let formattedText = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            // Gérer les sauts de ligne pour un rendu propre
            formattedText = formattedText.replace(/\n/g, '<br>');

            let i = 0;
            const fullTextContent = text.replace(/\n/g, ' ');

            targetElement.innerHTML = '';

            // Lecture vocale juste avant le début de la frappe
            speak(text);

            const typingInterval = setInterval(() => {
                if (i < fullTextContent.length) {
                    // Pour la simulation, on utilise textContent
                    targetElement.textContent += fullTextContent.charAt(i);
                    i++;
                } else {
                    clearInterval(typingInterval);
                    // Appliquer le formatage final (gras, sauts de ligne)
                    targetElement.innerHTML = formattedText;
                    resolve();
                }
            }, 30);
        });
    }

    // --- NOUVELLE FONCTION : AFFICHER LES BOUTONS DE DÉMARRAGE RAPIDE ---
    const quickStartIntents = [
        { label: "Conseil Téléphone 📱", question: "quel téléphone me conseilles-tu ?" },
        { label: "Conseil Ordinateur 💻", question: "quel ordinateur est le meilleur ?" },
        { label: "Info Livraison 🚚", question: "comment fonctionne la livraison ?" },
        { label: "Prix d'un Produit 💰", question: "prix produit" },
    ];

    function displayQuickStartButtons() {
        const buttonContainer = document.createElement('div');
        buttonContainer.classList.add('quick-start-container');

        quickStartIntents.forEach(intent => {
            const button = document.createElement('button');
            button.classList.add('btn', 'quick-start-btn');
            button.textContent = intent.label;

            button.addEventListener('click', () => {
                assistantInput.value = intent.question;
                sendMessage();
            });

            buttonContainer.appendChild(button);
        });

        assistantChatbox.appendChild(buttonContainer);
        assistantChatbox.scrollTop = assistantChatbox.scrollHeight;
    }

    // ✅ NOUVELLE FONCTION : AFFICHER LES BOUTONS DE LIENS DE NAVIGATION RAPIDE
    function displayAssistantLinksButtons(links) {
        const buttonContainer = document.createElement('div');
        buttonContainer.classList.add('quick-start-container');

        links.forEach(link => {
            const button = document.createElement('a');
            button.href = link.url;
            button.classList.add('btn', 'quick-start-btn', 'link-btn');
            button.textContent = link.label;

            buttonContainer.appendChild(button);
        });

        assistantChatbox.appendChild(buttonContainer);
        assistantChatbox.scrollTop = assistantChatbox.scrollHeight;
    }

    // --- NOUVELLE FONCTION : AFFICHER LES BOUTONS DE CONTACT WHATSAPP ---
    function displayWhatsappContactButtons(contacts, userQuestion) {
        const buttonContainer = document.createElement('div');
        buttonContainer.classList.add('whatsapp-contact-container');

        const encodedQuestion = encodeURIComponent(`Bonjour, j'ai une question non résolue par l'assistant : "${userQuestion}"`);

        contacts.forEach(contact => {
            const button = document.createElement('a');
            button.href = `https://wa.me/${contact.number.replace('+', '')}?text=${encodedQuestion}`;
            button.target = '_blank';
            button.classList.add('btn', 'whatsapp-btn');
            button.innerHTML = `<i class="fab fa-whatsapp"></i> Contacter ${contact.label}`;

            buttonContainer.appendChild(button);
        });

        assistantChatbox.appendChild(buttonContainer);
        assistantChatbox.scrollTop = assistantChatbox.scrollHeight;
    }

    // ✅ FONCTION sendMessage CORRIGÉE (Lignes 430-482)
    async function sendMessage() {
        const question = assistantInput.value.trim();
        if (!question) return;

        lastUserQuestion = question; // Sauvegarde de la question

        // Arrêter la parole si l'utilisateur envoie un nouveau message
        if (synth.speaking) {
            synth.cancel();
        }

        appendMessage(question, 'user');
        assistantInput.value = '';
        assistantInput.focus();

        // Créer l'élément de message de l'assistant avec le bouton haut-parleur
        const loadingMessageContainer = appendMessage('', 'assistant').parentNode;
        const loadingTextElement = loadingMessageContainer.querySelector('span:last-child');
        loadingTextElement.innerHTML = '<span class="loading-dots">...</span>';

        try {
            const response = await fetch('/api/assistant', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: question })
            });
            const data = await response.json();

            // Mettre à jour l'élément de texte après le chargement

            // 1. Affiche la réponse standard
            if (data.redirect) {
                await typeResponse(data.response, loadingTextElement);
                setTimeout(() => {
                    window.location.href = data.redirect;
                }, 1000);
            } else {
                // Affichage de la réponse normale (salutation, produit, etc.)
                await typeResponse(data.response, loadingTextElement);
            }

            // --- GESTION DES ACTIONS SPÉCIFIQUES ---

            // 2. Afficher les boutons de navigation rapide si l'intention est guide_vers_page
            if (data.intent === 'guide_vers_page' && data.assistant_links && data.assistant_links.length > 0) {
                displayAssistantLinksButtons(data.assistant_links);
            }

            // 3. Afficher les boutons de contact WA et les quick start buttons si l'intention est 'defaut' ou 'service_client_probleme'
            if (data.intent === 'defaut' || data.intent === 'service_client_probleme') {
                
                // Afficher les boutons WhatsApp si le serveur les a renvoyés
                if (data.contact_wa && data.contact_wa.length > 0) {
                    displayWhatsappContactButtons(data.contact_wa, lastUserQuestion);
                }
                
                // Ajouter les boutons de démarrage rapide pour guider l'utilisateur
                displayQuickStartButtons(); 
            }

        } catch (error) {
            loadingTextElement.innerHTML = 'Erreur de connexion avec Chérif.';
            console.error("Erreur API Chérif:", error);
            // Lire l'erreur vocalement
            speak("Erreur de connexion avec Chérif.");
        }
    }

    // ===================================================================
    // 🎤 --- IMPLEMENTATION DU MICROPHONE (Reconnaissance Vocale RÉELLE) --- 🎤
    // ===================================================================

    // Vérifie la compatibilité de l'API Web Speech Recognition (nécessite HTTPS ou localhost)
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    let recognition = null;
    let isListening = false;

    if (SpeechRecognition && micButton) {
        recognition = new SpeechRecognition();
        recognition.continuous = false; // Arrête après une seule phrase
        recognition.lang = 'fr-FR'; // Langue : Français
        recognition.interimResults = false; // Ne donne pas de résultats intermédiaires

        // --- Événements de la Reconnaissance ---

        // Quand le micro est prêt
        recognition.onstart = () => {
            micButton.textContent = '🔴'; // Icône d'enregistrement
            micButton.classList.add('recording');
            assistantInput.placeholder = "Écoute en cours... Parlez maintenant...";
            isListening = true;
        };

        // Quand la reconnaissance donne un résultat (parole reconnue)
        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;

            // Met le texte dans le champ de saisie
            assistantInput.value = transcript;

            // Simule l'envoi immédiat après la reconnaissance (comme l'utilisateur appuie sur Entrée)
            sendMessage();

            // Les événements onend/onerror gèreront la réinitialisation de l'UI
        };

        // Quand le micro se déconnecte (fin de la parole ou stop manuel)
        recognition.onend = () => {
            micButton.textContent = '🎙️';
            micButton.classList.remove('recording');
            assistantInput.placeholder = "Posez votre question...";
            isListening = false;
        };

        // En cas d'erreur
        recognition.onerror = (event) => {
            console.error('Erreur de reconnaissance vocale:', event.error);
            micButton.textContent = '🎙️';
            micButton.classList.remove('recording');
            assistantInput.placeholder = "Posez votre question...";
            isListening = false;

            // Informer l'utilisateur de l'erreur (ex: permission refusée)
            appendMessage(`🎙️ Erreur: ${event.error}. Assurez-vous d'avoir autorisé le microphone.`, 'assistant');
        };

        // --- Logique du Bouton Micro ---
        micButton.addEventListener('click', () => {
            if (!isListening) {
                try {
                    recognition.start();
                } catch (e) {
                    console.error('Erreur de démarrage du micro:', e);
                    appendMessage('🎙️ Impossible d\'activer le micro. Veuillez vérifier vos autorisations.', 'assistant');
                }
            } else {
                recognition.stop(); // Arrête l'écoute manuellement
            }
        });

    } else if (micButton) {
        // Le navigateur ne supporte pas l'API ou n'est pas en HTTPS
        micButton.style.display = 'none'; // Cache le bouton s'il n'est pas supporté
        console.warn("La reconnaissance vocale n'est pas supportée ou nécessite HTTPS.");
    }

    // FIN DE L'IMPLEMENTATION MICROPHONE
    // ===================================================================

    if (assistantContainer) {

        // Logique d'ouverture/fermeture du Bouton
        if (toggleCherifBtn && cherifWindow) {
            toggleCherifBtn.addEventListener('click', () => {
                cherifWindow.classList.toggle('is-active');
                toggleCherifBtn.textContent = cherifWindow.classList.contains('is-active') ? '❌' : '🤖';

                if (cherifWindow.classList.contains('is-active')) {
                    assistantInput.focus();

                    // Message d'accueil et Boutons de Démarrage Rapide
                    if (!cherifWindow.dataset.welcomed) {
                        const welcomeMessage = "Bonjour ! Je suis **Chérif**, votre assistant expert en électronique. Voici quelques sujets que je maîtrise :";

                        // Utiliser une version simple de appendMessage qui n'a pas besoin du speaker pour l'intro
                        const introMessageContainer = document.createElement('div');
                        introMessageContainer.classList.add('chat-message', 'assistant');
                        introMessageContainer.innerHTML = `<span>🤖 </span><span>${welcomeMessage}</span>`;
                        assistantChatbox.appendChild(introMessageContainer);

                        displayQuickStartButtons();
                        cherifWindow.dataset.welcomed = 'true';

                        // Lire le message d'accueil
                        speak(welcomeMessage);
                    }
                } else {
                    // Arrêter la lecture vocale à la fermeture de la fenêtre
                    if (synth.speaking) {
                        synth.cancel();
                    }
                    // Arrêter le micro si en cours d'écoute
                    if (isListening) {
                        recognition.stop();
                    }
                }
            });
        }

        // Envoi via le bouton '➡️'
        if (sendButton) {
            sendButton.addEventListener('click', sendMessage);
        }

        // Envoi via la touche Entrée
        if (assistantInput) {
            assistantInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    sendMessage();
                    e.preventDefault();
                }
            });
        }
    }

    // --- 4. Logique du Panier (MODIFIÉE pour l'enregistrement Admin) ---

    if (document.querySelector('.cart-container')) {
        renderCart();

        // Gestion du bouton 'Passer à la Commande'
        if (showCheckoutBtn) {
            showCheckoutBtn.addEventListener('click', () => {
                if (getTotalItemCount() > 0) {
                    checkoutFormContainer.style.display = 'block';
                    showCheckoutBtn.style.display = 'none';
                } else {
                    alert("Votre panier est vide. Veuillez ajouter des articles avant de commander.");
                }
            });
        }

        // Gestion de la soumission du formulaire de commande (MODIFIÉ)
        if (checkoutForm) {
            checkoutForm.addEventListener('submit', async function(e) {
                e.preventDefault();

                const clientName = document.getElementById('client-name').value;
                const clientQuartier = document.getElementById('client-quartier').value;

                let grandTotal = 0;
                for (const productId in cart) {
                    grandTotal += parseFloat(cart[productId].prix) * cart[productId].quantity;
                }

                if (grandTotal === 0) {
                    alert("Votre panier est vide. Impossible de commander.");
                    return;
                }

                // --- LOGIQUE D'ENREGISTREMENT ET ENVOI ---

                // 1. Enregistrement de la commande via l'API (pour l'administration)
                // L'enregistrement est tenté. Le succès n'empêche pas l'envoi WhatsApp.
                const isRecorded = await recordOrderOnAPI(clientName, clientQuartier, grandTotal);

                if (isRecorded) {
                    console.log("Commande enregistrée dans l'administration.");
                } else {
                    // NOTE : Ne pas alerter sur l'échec de l'enregistrement de l'API si l'envoi WhatsApp est imminent.
                    // alert("Alerte: La commande n'a pas pu être enregistrée dans l'administration. Veuillez vérifier manuellement !");
                }


                // 2. Envoi de la commande WhatsApp (comme avant)
                const message = buildWhatsappMessage(clientName, clientQuartier, grandTotal);
                const selectedNumber = getPrimaryWhatsappNumber();

                if (selectedNumber) {
                    const whatsappUrl = `https://wa.me/${selectedNumber}?text=${message}`;
                    window.open(whatsappUrl, '_blank');

                    // Vider le panier uniquement si l'enregistrement ou l'envoi a réussi (ici, WA est la confirmation finale)
                    cart = {};
                    updateCart();
                } else {
                    alert("Erreur: Le numéro WhatsApp n'est pas configuré. Veuillez contacter l'administrateur.");
                }
            });
        }
    }

    // Initialiser l'état des haut-parleurs au chargement
    setSpeakerState(window.SPEAKER_ACTIVE);
});
