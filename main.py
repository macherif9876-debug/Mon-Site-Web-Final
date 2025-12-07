from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from supabase import create_client, Client
from functools import wraps
import os
import uuid 
import io 
from werkzeug.utils import secure_filename 
from flask import url_for 
from datetime import datetime

# ===================================================================
# --- MODIFICATIONS CRUCIALES POUR LE DÉPLOIEMENT ---

# 1. Lire l'URL et la clé Supabase depuis les variables d'environnement
#    Render/Heroku vous demandera de définir ces variables.
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY") 
# NOTE: Nous utilisons "SUPABASE_ANON_KEY" pour la clarté, 
# même si le nom était "SUPABASE_KEY" avant.

# Initialisation du client Supabase
# Si les clés ne sont pas définies (par exemple, en local sans fichier .env), le programme plantera ici.
# Ce comportement est normal en déploiement.
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Configuration Flask ---
app = Flask(__name__)

# 2. Rendre la clé secrète OBLIGATOIREMENT lue de l'environnement
#    La valeur par défaut est supprimée pour forcer son utilisation en production.
app.secret_key = os.environ.get("FLASK_SECRET_KEY") 

app.config['SUPABASE_URL'] = SUPABASE_URL
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# --- FIN DES MODIFICATIONS CRUCIALES ---
# ===================================================================

STORAGE_BUCKET = "images_produits"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# ✅ Numéros WhatsApp pour la commande (sans le '+' pour l'API wa.me)
WHATSAPP_NUMBERS = [
    "224621822134", 
    "224625480987"
]
PRIMARY_WHATSAPP_NUMBER = WHATSAPP_NUMBERS[0] if WHATSAPP_NUMBERS else None


# --- LOGIQUE DES CATÉGORIES ---

def get_categories_list():
    """Retourne la liste des catégories/types de produits."""
    return [
        {'name': 'Téléphones', 'slug': 'telephone', 'icon': '📱'},
        {'name': 'Ordinateurs', 'slug': 'ordinateur', 'icon': '💻'},
        {'name': 'Accessoires', 'slug': 'accessoire', 'icon': '🎧'},
    ]

@app.context_processor
def inject_globals():
    """Rend les types de produits et le numéro WhatsApp PRINCIPAL disponibles globalement dans les templates Jinja."""
    return dict(
        categories=get_categories_list(),
        # Injecter le numéro principal pour base.html et cart.html
        whatsapp_number=PRIMARY_WHATSAPP_NUMBER 
    )


# --- Fonctions utilitaires ---
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_image_to_supabase(file, product_id):
    if file and allowed_file(file.filename):
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        # Générer un nom de fichier unique
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        # Chemin de stockage: produits/<ID_produit>/<NOM_UNIQUE>.ext
        storage_path = f"produits/{product_id}/{unique_filename}" 
        
        file.seek(0)
        file_content = file.read()
        
        try:
            # Upload du fichier au Storage
            supabase.storage.from_(STORAGE_BUCKET).upload(storage_path, file_content, file_options={"content-type": file.mimetype})
            # Récupérer l'URL publique
            public_url = supabase.storage.from_(STORAGE_BUCKET).get_public_url(storage_path)
            return public_url
        except Exception as e:
            print(f"Erreur d'upload Supabase: {e}")
            return None
    return None

try:
    from assistant_data import get_assistant_response 
except ImportError:
    def get_assistant_response(question):
        return {"response": "L'assistant n'est pas configuré.", "intent": "none"}

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = session.get('user')
        if not user:
            return redirect(url_for('login', error="Accès refusé. Veuillez vous connecter pour accéder à l'administration."))
        return f(*args, **kwargs)
    return decorated_function

# --- NOUVEAUX ÉLÉMENTS POUR LE CONTENU 'À PROPOS' ---
ABOUT_TABLE = 'about_page_content' 

def get_or_create_about_content():
    """Récupère l'unique ligne de contenu 'À Propos' ou la crée par défaut."""
    
    default_content = {
        'mission_title': "Notre Mission : La Tech Facile en Guinée",
        'mission_text': "Bienvenue chez Bon Coin Bon Prix ! Notre concept est simple : rendre la technologie de qualité (téléphones, ordinateurs, accessoires) accessible à tous, sans compromis sur le prix. Nous sélectionnons chaque article pour son authenticité et sa durabilité, vous garantissant le Bon Prix pour le Bon Coin.",
        'commitment_title': "Notre Engagement Qualité",
        'commitment_list_text': "Produits 100% Authentiques, Prix Justes et Compétitifs, Service Client Local, Livraison Fiable",
        'whatsapp_number': PRIMARY_WHATSAPP_NUMBER,
        'email': "contact@boncoinbonprix.com"
    }

    try:
        response = supabase.table(ABOUT_TABLE).select('*').limit(1).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]
            
    except Exception as e:
        print(f"DEBUG ERREUR Supabase (About): Échec de la récupération du contenu: {e}")

    try:
        insert_response = supabase.table(ABOUT_TABLE).insert(default_content).execute()
        
        if insert_response.data:
            print("Entrée 'À Propos' par défaut créée sur Supabase.")
            return insert_response.data[0] 
        
    except Exception as e:
        print(f"DEBUG AVERTISSEMENT: Échec de l'insertion par défaut (la table n'existe peut-être pas ou RLS est activé). Utilisation des valeurs locales.")
        pass 
        
    return default_content

# --- Fonctions de récupération de données ---
def get_products_with_images(limit=None): 
    """Récupère tous les produits pour la page d'accueil ou l'administration."""
    
    query = supabase.table('produits')
            
    # Récupérer l'URL de l'image principale
    select_string = "*, images_produits!inner(url, est_principale)" 
    query = query.select(select_string)
    
    if limit:
        query = query.limit(limit) 

    try:
        products_response = query.execute()
    except Exception as e:
        print(f"DEBUG ERREUR Supabase: Échec de l'exécution de la requête: {e}")
        return []

    products = []
    if not products_response.data:
        return []
    
    category_map = {c['slug']: c['name'] for c in get_categories_list()}

    for p in products_response.data:
        image_data = p.pop('images_produits', None) 
        image_url = None
        
        # Logique de récupération de l'image principale
        if image_data and isinstance(image_data, list):
             main_image = next((img['url'] for img in image_data if img.get('est_principale', False)), None)
             image_url = main_image
        
        p['image_url'] = image_url if image_url else url_for('static', filename='images/default_product.jpg')
        p['category_name'] = category_map.get(p.get('type'), 'Divers') 
        products.append(p)
    
    return products

# --- Routes Publiques ---
@app.route('/')
def index():
    """Page d'accueil : Affiche tous les produits (limité à 8)."""
    products = get_products_with_images(limit=8) 
    return render_template('index.html', products=products)

@app.route('/product/<uuid:product_id>')
def product_detail(product_id):
    """Affiche les détails d'un produit, y compris les images multiples."""
    str_product_id = str(product_id)
    
    try:
        # 1. Récupérer le produit (y compris le stock et toutes les images)
        product_res = supabase.table('produits').select('*, images_produits(id, url, est_principale)').eq('id', str_product_id).single().execute()
        product_data = product_res.data
        
        if not product_data:
            return "Produit non trouvé", 404
            
        images_res = product_data.pop('images_produits', [])

        # 2. Séparer l'image principale et les images de détail
        default_url = url_for('static', filename='images/default_product.jpg')
        main_image = next((img['url'] for img in images_res if img.get('est_principale', False)), default_url)
        detail_images = [img for img in images_res if not img.get('est_principale', False)] # Garder l'ID pour la suppression future

        product_data['main_image'] = main_image
        product_data['detail_images'] = detail_images

        # Ajouter le nom de la catégorie pour l'affichage
        category_map = {c['slug']: c['name'] for c in get_categories_list()}
        product_data['category_name'] = category_map.get(product_data.get('type'), 'Divers') 
        
        return render_template('product_detail.html', product=product_data)

    except Exception as e:
        print(f"DEBUG ERREUR ROUTE DETAIL: {e}")
        return "Erreur lors de la récupération des détails du produit", 500

@app.route('/category/<category_name>')
def category_page(category_name):
    """Affiche les produits par type en filtrant les données en Python."""
    
    category_titles = {
        'telephone': 'Téléphones 📱',
        'ordinateur': 'Ordinateurs 💻',
        'accessoire': 'Accessoires 🎧'
    }
    
    if category_name not in category_titles:
        return redirect(url_for('index')) 

    try:
        all_products = get_products_with_images() 
        
        filtered_products = [
            p for p in all_products 
            if p.get('type') == category_name
        ]
        
        template_name = 'category_view.html' 

        return render_template(
            template_name, 
            products=filtered_products, 
            title=category_titles[category_name],
            category=category_name
        )
    except Exception as e:
        print(f"DEBUG ERREUR ROUTE: Erreur lors de la récupération/filtrage des données: {e}")
        return render_template(
            'category_view.html', 
            products=[], 
            title=category_titles.get(category_name, 'Catégorie'), 
            error=f"Erreur lors du traitement des produits: {e}"
        )

# --- Routes d'Authentification / Assistant ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        try:
            user_response = supabase.auth.sign_in_with_password({"email": email, "password": password})
            user_data = user_response.user
            
            if user_data:
                session['user'] = {'id': user_data.id, 'email': user_data.email} 
                return redirect(url_for('admin_dashboard'))
            else:
                error = "Email ou mot de passe incorrect."
        except Exception as e:
            error_message = str(e)
            error = f"Erreur d'authentification : {error_message}"
        
        return render_template('login.html', error=error)
    return render_template('login.html', error=request.args.get('error'))


@app.route('/logout')
def logout():
    supabase.auth.sign_out()
    session.pop('user', None)
    return redirect(url_for('index'))

@app.route('/cart')
def cart():
    """Page du Panier."""
    return render_template('cart.html')

@app.route('/about')
def about():
    """
    Page À Propos : Récupère le contenu modifiable depuis Supabase.
    """
    about_content = get_or_create_about_content()
    return render_template('about.html', about_content=about_content)

# --- NOUVELLE ROUTE ADMIN POUR ÉDITER LE CONTENU 'À PROPOS' (VÉRIFIÉE) ---
@app.route('/admin/about/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_about():
    
    about_content = get_or_create_about_content()
    error = None
    success = None
    
    # Récupérer products_count de manière sécurisée pour l'héritage du template admin
    try:
        products_count_res = supabase.table('produits').select('id', count='exact').execute()
        products_count = products_count_res.count if products_count_res.count is not None else 0
    except Exception:
        products_count = 0 
    
    if request.method == 'POST':
        try:
            updated_data = {
                'mission_title': request.form['mission_title'],
                'mission_text': request.form['mission_text'],
                'commitment_title': request.form['commitment_title'],
                'commitment_list_text': request.form['commitment_list_text'],
                'whatsapp_number': request.form['whatsapp_number'],
                'email': request.form['email']
            }
            
            # Mise à jour de la première (et unique) ligne
            if 'id' in about_content:
                supabase.table(ABOUT_TABLE).update(updated_data).eq('id', about_content['id']).execute()
            else:
                supabase.table(ABOUT_TABLE).update(updated_data).limit(1).execute() 
                
            success = "Le contenu de la page 'À Propos' a été mis à jour avec succès !"
            # Redirection après le POST pour éviter l'envoi multiple
            return redirect(url_for('admin_edit_about', success=success)) 

        except Exception as e:
            error = f"Erreur lors de la mise à jour du contenu: {e}"
            # Utiliser les données du formulaire en cas d'erreur
            about_content = about_content.copy() 
            about_content.update(request.form)
    
    # Recharger le contenu mis à jour si on revient avec un succès dans l'URL (GET)
    if request.args.get('success'):
        success = request.args.get('success')
        about_content = get_or_create_about_content()
        

    return render_template('admin/edit_about.html', 
                           about_content=about_content,
                           error=error,
                           success=success,
                           products_count=products_count)


@app.route('/api/assistant', methods=['POST'])
def handle_assistant():
    data = request.get_json()
    user_question = data.get('question', '')
    
    if not user_question:
        return jsonify({"response": "Veuillez poser une question."})

    response_data = get_assistant_response(user_question)
    
    if response_data["intent"] == "port_secrete":
        return jsonify({
            "response": "🔑 Accès Administrateur Déverrouillé. Redirection...",
            "redirect": url_for('login')
        })
    # ✅ J'ajoute les numéros WhatsApp pour le JS
    if response_data["intent"] == "defaut":
        response_data["contact_wa"] = [
            {"label": "Support Principal", "number": WHATSAPP_NUMBERS[0]},
            {"label": "Support Secondaire", "number": WHATSAPP_NUMBERS[1]}
        ]
        
    return jsonify({
        "response": response_data["response"],
        "intent": response_data["intent"],
        "contact_wa": response_data.get("contact_wa", [])
    })


# --- NOUVELLE ROUTE API : ENREGISTRER LA COMMANDE (UNIFIÉ) ---
@app.route('/api/order/submit', methods=['POST'])
def submit_order():
    data = request.get_json()
    cart_items = data.get('cart_items', [])
    
    if not cart_items:
        return jsonify({"success": False, "message": "Le panier est vide."}), 400
        
    try:
        # Enregistrer la commande
        order_data = {
            'produits_json': cart_items, # Stocke la liste des produits dans le panier
            # Utilisez datetime.now().isoformat() pour le timestamp si 'now()' pose problème
            'date_commande': datetime.now().isoformat(), 
            'statut': 'En attente WhatsApp' # Statut initial
        }
        
        response = supabase.table('commandes').insert(order_data).execute()
        
        if response.data:
            order_id = response.data[0].get('id', 'N/A')
            return jsonify({"success": True, "message": "Commande enregistrée en attente.", "order_id": order_id})
        else:
            raise Exception("Aucune donnée de commande retournée.")

    except Exception as e:
        print(f"DEBUG ERREUR ENREGISTREMENT COMMANDE: {e}")
        return jsonify({"success": False, "message": f"Erreur serveur: {e}"}), 500


# --- Routes Administrateur ---

@app.route('/admin')
@admin_required
def admin_dashboard():
    products_count_res = supabase.table('produits').select('id', count='exact').execute()
    products_count = products_count_res.count if products_count_res.count is not None else 0
    return render_template('admin/dashboard.html', products_count=products_count)

@app.route('/admin/products', methods=['GET'])
@admin_required
def admin_manage_products():
    search_query = request.args.get('search', '')
    
    products_count_res = supabase.table('produits').select('id', count='exact').execute()
    products_count = products_count_res.count if products_count_res.count is not None else 0
    
    if search_query:
        try:
            products_response = supabase.table('produits').select("*, images_produits(url, est_principale)").like('nom', f'%{search_query}%').execute()
            
            products_data = products_response.data
            products = []
            category_map = {c['slug']: c['name'] for c in get_categories_list()}
            
            for p in products_data:
                image_data = p.pop('images_produits', None) 
                image_url = None
                if image_data and isinstance(image_data, list):
                    main_image = next((img['url'] for img in image_data if img.get('est_principale', False)), None)
                    image_url = main_image
                    
                p['image_url'] = image_url if image_url else url_for('static', filename='images/default_product.jpg')
                p['category_name'] = category_map.get(p.get('type'), 'Divers') 
                products.append(p)
            
        except Exception as e:
            print(f"DEBUG ERREUR RECHERCHE: {e}")
            products = []
            
        return render_template('admin/manage_products.html', products=products, search_query=search_query, products_count=products_count)

    else:
        products = get_products_with_images()
        return render_template('admin/manage_products.html', products=products, search_query=search_query, products_count=products_count)


@app.route('/admin/products/add', methods=['GET', 'POST'])
@admin_required
def admin_add_product():
    products_count_res = supabase.table('produits').select('id', count='exact').execute()
    products_count = products_count_res.count if products_count_res.count is not None else 0
    
    if request.method == 'POST':
        try:
            product_data = {
                'nom': request.form['nom'],
                'description': request.form['description'],
                'prix_gnf': float(request.form['prix']),
                'type': request.form['type'],
                'stock': int(request.form.get('stock', 0)),
            }
            response = supabase.table('produits').insert(product_data).execute()
            
            if response.data and response.data[0].get('id'):
                product_id = str(response.data[0]['id'])
                
                # Gestion de l'image principale
                if 'image_file' in request.files and request.files['image_file'].filename != '':
                    file = request.files['image_file']
                    
                    image_url = upload_image_to_supabase(file, product_id)
                    
                    if image_url:
                        # Insère l'image principale
                        supabase.table('images_produits').insert({
                            'produit_id': product_id,
                            'url': image_url,
                            'est_principale': True
                        }).execute()
                    else:
                        raise Exception("Échec de l'upload de l'image principale ou format non autorisé.")
                
                return redirect(url_for('admin_manage_products'))
            else:
                error = f"Erreur lors de l'ajout du produit: {response.data}"
        except Exception as e:
            error = f"Erreur: {e}"
        
        return render_template('admin/add_product.html', 
                               error=error,
                               product=None, 
                               current_image_url=None,
                               products_count=products_count
                               ) 
        
    return render_template('admin/add_product.html', product=None, current_image_url=None, products_count=products_count)


@app.route('/admin/products/edit/<uuid:product_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_product(product_id):
    products_count_res = supabase.table('produits').select('id', count='exact').execute()
    products_count = products_count_res.count if products_count_res.count is not None else 0
    
    str_product_id = str(product_id)
    
    # Récupération du produit
    product_res = supabase.table('produits').select('*').eq('id', str_product_id).single().execute()
    product = product_res.data
    
    if not product:
        return "Produit non trouvé", 404
        
    # Récupération de l'image principale actuelle pour l'affichage
    current_image_res = supabase.table('images_produits').select('url').eq('produit_id', str_product_id).eq('est_principale', True).limit(1).execute().data
    current_image_url = current_image_res[0]['url'] if current_image_res else ''
        
    if request.method == 'POST':
        try:
            product_data = {
                'nom': request.form['nom'],
                'description': request.form['description'],
                'prix_gnf': float(request.form['prix']),
                'type': request.form['type'],
                'stock': int(request.form.get('stock', 0)),
            }
            # Mise à jour des données du produit
            supabase.table('produits').update(product_data).eq('id', str_product_id).execute()
            
            # LOGIQUE D'UPLOAD DE L'IMAGE PRINCIPALE
            if 'image_file' in request.files and request.files['image_file'].filename != '':
                file = request.files['image_file']
                
                new_image_url = upload_image_to_supabase(file, str_product_id)
                
                if new_image_url:
                    if current_image_url:
                        # Mise à jour de l'URL existante
                        supabase.table('images_produits').update({'url': new_image_url}).eq('produit_id', str_product_id).eq('est_principale', True).execute()
                    else:
                        # Insertion si l'image principale n'existait pas
                        supabase.table('images_produits').insert({
                            'produit_id': str_product_id,
                            'url': new_image_url,
                            'est_principale': True
                        }).execute()
                else:
                    raise Exception("Échec de l'upload de l'image principale ou format non autorisé.")

            return redirect(url_for('admin_manage_products'))
            
        except Exception as e:
            error = f"Erreur lors de la modification: {e}"
            return render_template('admin/add_product.html', product=product, error=error, current_image_url=current_image_url, products_count=products_count)
            
    return render_template('admin/add_product.html', product=product, current_image_url=current_image_url, products_count=products_count) 


@app.route('/admin/orders')
@admin_required
def admin_manage_orders():
    products_count_res = supabase.table('produits').select('id', count='exact').execute()
    products_count = products_count_res.count if products_count_res.count is not None else 0
    
    try:
        orders_res = supabase.table('commandes').select('*').order('date_commande', desc=True).execute()
        orders = orders_res.data
        
        return render_template('admin/manage_orders.html', orders=orders, products_count=products_count)

    except Exception as e:
        print(f"DEBUG ERREUR GESTION COMMANDES: {e}")
        return render_template('admin/manage_orders.html', orders=[], error=f"Erreur de connexion à la base de données: {e}", products_count=products_count)


@app.route('/admin/orders/update_status/<uuid:order_id>', methods=['POST'])
@admin_required
def admin_update_order_status(order_id):
    new_status = request.form.get('status')
    if not new_status:
        return "Statut manquant", 400
        
    try:
        supabase.table('commandes').update({'statut': new_status}).eq('id', str(order_id)).execute()
        return redirect(url_for('admin_manage_orders'))
    except Exception as e:
        return f"Erreur lors de la mise à jour: {e}", 500


@app.route('/admin/products/images/<uuid:product_id>', methods=['GET', 'POST'])
@admin_required
def admin_manage_detail_images(product_id):
    products_count_res = supabase.table('produits').select('id', count='exact').execute()
    products_count = products_count_res.count if products_count_res.count is not None else 0
    
    str_product_id = str(product_id)
    
    # 1. Récupérer le produit et les images existantes
    product_res = supabase.table('produits').select('nom').eq('id', str_product_id).single().execute()
    product = product_res.data
    
    if not product:
        return "Produit non trouvé", 404
        
    current_detail_images_res = supabase.table('images_produits').select('id, url, est_principale').eq('produit_id', str_product_id).eq('est_principale', False).execute().data
    
    error = None

    if request.method == 'POST':
        # 2. LOGIQUE D'UPLOAD D'UNE NOUVELLE IMAGE DE DÉTAIL
        if 'detail_image_file' in request.files and request.files['detail_image_file'].filename != '':
            detail_file = request.files['detail_image_file']
            
            new_detail_image_url = upload_image_to_supabase(detail_file, str_product_id)
            
            if new_detail_image_url:
                try:
                    # Insère la nouvelle image comme image de détail
                    supabase.table('images_produits').insert({
                        'produit_id': str_product_id,
                        'url': new_detail_image_url,
                        'est_principale': False # C'est une image de détail
                    }).execute()
                    # Redirection GET pour effacer le POST et actualiser la liste
                    return redirect(url_for('admin_manage_detail_images', product_id=product_id)) 
                except Exception as e:
                    error = f"Erreur d'enregistrement dans la base de données: {e}"
            else:
                error = "Échec de l'upload de l'image ou format non autorisé."
        else:
            error = "Veuillez sélectionner un fichier à télécharger."

    # Affichage du formulaire et des images existantes
    return render_template('admin/manage_detail_images.html', 
                           product=product, 
                           product_id=product_id,
                           detail_images=current_detail_images_res,
                           error=error,
                           products_count=products_count)


@app.route('/admin/images/delete_detail/<uuid:image_id>', methods=['POST'])
@admin_required
def admin_delete_image_detail(image_id):
    try:
        image_res = supabase.table('images_produits').select('produit_id').eq('id', str(image_id)).single().execute()
        image_data = image_res.data
        
        if image_data:
            product_id = image_data['produit_id']
            
            supabase.table('images_produits').delete().eq('id', str(image_id)).execute()
            
            return redirect(url_for('admin_manage_detail_images', product_id=product_id))
        else:
             return "Image non trouvée", 404

    except Exception as e:
        print(f"DEBUG ERREUR SUPPRESSION IMAGE: {e}")
        return "Erreur lors de la suppression de l'image", 500


@app.route('/admin/products/delete/<uuid:product_id>', methods=['POST'])
@admin_required
def admin_delete_product(product_id):
    supabase.table('produits').delete().eq('id', str(product_id)).execute()
    return redirect(url_for('admin_manage_products'))


if __name__ == '__main__':
    # REMPLACÉ PAR LA LIGNE GUNICORN DANS LE PROCFILE LORS DU DÉPLOIEMENT
    # app.run(debug=True)
    # Laissez cette ligne pour le test local si nécessaire, mais Render utilisera Gunicorn.
    pass
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from supabase import create_client, Client
from functools import wraps
import os
import uuid 
import io 
from werkzeug.utils import secure_filename 
from flask import url_for 
from datetime import datetime

# ===================================================================
# --- MODIFICATIONS CRUCIALES POUR LE DÉPLOIEMENT ---

# 1. Lire l'URL et la clé Supabase depuis les variables d'environnement
#    Render/Heroku vous demandera de définir ces variables.
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY") 
# NOTE: Nous utilisons "SUPABASE_ANON_KEY" pour la clarté, 
# même si le nom était "SUPABASE_KEY" avant.

# Initialisation du client Supabase
# Si les clés ne sont pas définies (par exemple, en local sans fichier .env), le programme plantera ici.
# Ce comportement est normal en déploiement.
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Configuration Flask ---
app = Flask(__name__)

# 2. Rendre la clé secrète OBLIGATOIREMENT lue de l'environnement
#    La valeur par défaut est supprimée pour forcer son utilisation en production.
app.secret_key = os.environ.get("FLASK_SECRET_KEY") 

app.config['SUPABASE_URL'] = SUPABASE_URL
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# --- FIN DES MODIFICATIONS CRUCIALES ---
# ===================================================================

STORAGE_BUCKET = "images_produits"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# ✅ Numéros WhatsApp pour la commande (sans le '+' pour l'API wa.me)
WHATSAPP_NUMBERS = [
    "224621822134", 
    "224625480987"
]
PRIMARY_WHATSAPP_NUMBER = WHATSAPP_NUMBERS[0] if WHATSAPP_NUMBERS else None


# --- LOGIQUE DES CATÉGORIES ---

def get_categories_list():
    """Retourne la liste des catégories/types de produits."""
    return [
        {'name': 'Téléphones', 'slug': 'telephone', 'icon': '📱'},
        {'name': 'Ordinateurs', 'slug': 'ordinateur', 'icon': '💻'},
        {'name': 'Accessoires', 'slug': 'accessoire', 'icon': '🎧'},
    ]

@app.context_processor
def inject_globals():
    """Rend les types de produits et le numéro WhatsApp PRINCIPAL disponibles globalement dans les templates Jinja."""
    return dict(
        categories=get_categories_list(),
        # Injecter le numéro principal pour base.html et cart.html
        whatsapp_number=PRIMARY_WHATSAPP_NUMBER 
    )


# --- Fonctions utilitaires ---
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_image_to_supabase(file, product_id):
    if file and allowed_file(file.filename):
        file_extension = file.filename.rsplit('.', 1)[1].lower()
        # Générer un nom de fichier unique
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        # Chemin de stockage: produits/<ID_produit>/<NOM_UNIQUE>.ext
        storage_path = f"produits/{product_id}/{unique_filename}" 
        
        file.seek(0)
        file_content = file.read()
        
        try:
            # Upload du fichier au Storage
            supabase.storage.from_(STORAGE_BUCKET).upload(storage_path, file_content, file_options={"content-type": file.mimetype})
            # Récupérer l'URL publique
            public_url = supabase.storage.from_(STORAGE_BUCKET).get_public_url(storage_path)
            return public_url
        except Exception as e:
            print(f"Erreur d'upload Supabase: {e}")
            return None
    return None

try:
    from assistant_data import get_assistant_response 
except ImportError:
    def get_assistant_response(question):
        return {"response": "L'assistant n'est pas configuré.", "intent": "none"}

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = session.get('user')
        if not user:
            return redirect(url_for('login', error="Accès refusé. Veuillez vous connecter pour accéder à l'administration."))
        return f(*args, **kwargs)
    return decorated_function

# --- NOUVEAUX ÉLÉMENTS POUR LE CONTENU 'À PROPOS' ---
ABOUT_TABLE = 'about_page_content' 

def get_or_create_about_content():
    """Récupère l'unique ligne de contenu 'À Propos' ou la crée par défaut."""
    
    default_content = {
        'mission_title': "Notre Mission : La Tech Facile en Guinée",
        'mission_text': "Bienvenue chez Bon Coin Bon Prix ! Notre concept est simple : rendre la technologie de qualité (téléphones, ordinateurs, accessoires) accessible à tous, sans compromis sur le prix. Nous sélectionnons chaque article pour son authenticité et sa durabilité, vous garantissant le Bon Prix pour le Bon Coin.",
        'commitment_title': "Notre Engagement Qualité",
        'commitment_list_text': "Produits 100% Authentiques, Prix Justes et Compétitifs, Service Client Local, Livraison Fiable",
        'whatsapp_number': PRIMARY_WHATSAPP_NUMBER,
        'email': "contact@boncoinbonprix.com"
    }

    try:
        response = supabase.table(ABOUT_TABLE).select('*').limit(1).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]
            
    except Exception as e:
        print(f"DEBUG ERREUR Supabase (About): Échec de la récupération du contenu: {e}")

    try:
        insert_response = supabase.table(ABOUT_TABLE).insert(default_content).execute()
        
        if insert_response.data:
            print("Entrée 'À Propos' par défaut créée sur Supabase.")
            return insert_response.data[0] 
        
    except Exception as e:
        print(f"DEBUG AVERTISSEMENT: Échec de l'insertion par défaut (la table n'existe peut-être pas ou RLS est activé). Utilisation des valeurs locales.")
        pass 
        
    return default_content

# --- Fonctions de récupération de données ---
def get_products_with_images(limit=None): 
    """Récupère tous les produits pour la page d'accueil ou l'administration."""
    
    query = supabase.table('produits')
            
    # Récupérer l'URL de l'image principale
    select_string = "*, images_produits!inner(url, est_principale)" 
    query = query.select(select_string)
    
    if limit:
        query = query.limit(limit) 

    try:
        products_response = query.execute()
    except Exception as e:
        print(f"DEBUG ERREUR Supabase: Échec de l'exécution de la requête: {e}")
        return []

    products = []
    if not products_response.data:
        return []
    
    category_map = {c['slug']: c['name'] for c in get_categories_list()}

    for p in products_response.data:
        image_data = p.pop('images_produits', None) 
        image_url = None
        
        # Logique de récupération de l'image principale
        if image_data and isinstance(image_data, list):
             main_image = next((img['url'] for img in image_data if img.get('est_principale', False)), None)
             image_url = main_image
        
        p['image_url'] = image_url if image_url else url_for('static', filename='images/default_product.jpg')
        p['category_name'] = category_map.get(p.get('type'), 'Divers') 
        products.append(p)
    
    return products

# --- Routes Publiques ---
@app.route('/')
def index():
    """Page d'accueil : Affiche tous les produits (limité à 8)."""
    products = get_products_with_images(limit=8) 
    return render_template('index.html', products=products)

@app.route('/product/<uuid:product_id>')
def product_detail(product_id):
    """Affiche les détails d'un produit, y compris les images multiples."""
    str_product_id = str(product_id)
    
    try:
        # 1. Récupérer le produit (y compris le stock et toutes les images)
        product_res = supabase.table('produits').select('*, images_produits(id, url, est_principale)').eq('id', str_product_id).single().execute()
        product_data = product_res.data
        
        if not product_data:
            return "Produit non trouvé", 404
            
        images_res = product_data.pop('images_produits', [])

        # 2. Séparer l'image principale et les images de détail
        default_url = url_for('static', filename='images/default_product.jpg')
        main_image = next((img['url'] for img in images_res if img.get('est_principale', False)), default_url)
        detail_images = [img for img in images_res if not img.get('est_principale', False)] # Garder l'ID pour la suppression future

        product_data['main_image'] = main_image
        product_data['detail_images'] = detail_images

        # Ajouter le nom de la catégorie pour l'affichage
        category_map = {c['slug']: c['name'] for c in get_categories_list()}
        product_data['category_name'] = category_map.get(product_data.get('type'), 'Divers') 
        
        return render_template('product_detail.html', product=product_data)

    except Exception as e:
        print(f"DEBUG ERREUR ROUTE DETAIL: {e}")
        return "Erreur lors de la récupération des détails du produit", 500

@app.route('/category/<category_name>')
def category_page(category_name):
    """Affiche les produits par type en filtrant les données en Python."""
    
    category_titles = {
        'telephone': 'Téléphones 📱',
        'ordinateur': 'Ordinateurs 💻',
        'accessoire': 'Accessoires 🎧'
    }
    
    if category_name not in category_titles:
        return redirect(url_for('index')) 

    try:
        all_products = get_products_with_images() 
        
        filtered_products = [
            p for p in all_products 
            if p.get('type') == category_name
        ]
        
        template_name = 'category_view.html' 

        return render_template(
            template_name, 
            products=filtered_products, 
            title=category_titles[category_name],
            category=category_name
        )
    except Exception as e:
        print(f"DEBUG ERREUR ROUTE: Erreur lors de la récupération/filtrage des données: {e}")
        return render_template(
            'category_view.html', 
            products=[], 
            title=category_titles.get(category_name, 'Catégorie'), 
            error=f"Erreur lors du traitement des produits: {e}"
        )

# --- Routes d'Authentification / Assistant ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        try:
            user_response = supabase.auth.sign_in_with_password({"email": email, "password": password})
            user_data = user_response.user
            
            if user_data:
                session['user'] = {'id': user_data.id, 'email': user_data.email} 
                return redirect(url_for('admin_dashboard'))
            else:
                error = "Email ou mot de passe incorrect."
        except Exception as e:
            error_message = str(e)
            error = f"Erreur d'authentification : {error_message}"
        
        return render_template('login.html', error=error)
    return render_template('login.html', error=request.args.get('error'))


@app.route('/logout')
def logout():
    supabase.auth.sign_out()
    session.pop('user', None)
    return redirect(url_for('index'))

@app.route('/cart')
def cart():
    """Page du Panier."""
    return render_template('cart.html')

@app.route('/about')
def about():
    """
    Page À Propos : Récupère le contenu modifiable depuis Supabase.
    """
    about_content = get_or_create_about_content()
    return render_template('about.html', about_content=about_content)

# --- NOUVELLE ROUTE ADMIN POUR ÉDITER LE CONTENU 'À PROPOS' (VÉRIFIÉE) ---
@app.route('/admin/about/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_about():
    
    about_content = get_or_create_about_content()
    error = None
    success = None
    
    # Récupérer products_count de manière sécurisée pour l'héritage du template admin
    try:
        products_count_res = supabase.table('produits').select('id', count='exact').execute()
        products_count = products_count_res.count if products_count_res.count is not None else 0
    except Exception:
        products_count = 0 
    
    if request.method == 'POST':
        try:
            updated_data = {
                'mission_title': request.form['mission_title'],
                'mission_text': request.form['mission_text'],
                'commitment_title': request.form['commitment_title'],
                'commitment_list_text': request.form['commitment_list_text'],
                'whatsapp_number': request.form['whatsapp_number'],
                'email': request.form['email']
            }
            
            # Mise à jour de la première (et unique) ligne
            if 'id' in about_content:
                supabase.table(ABOUT_TABLE).update(updated_data).eq('id', about_content['id']).execute()
            else:
                supabase.table(ABOUT_TABLE).update(updated_data).limit(1).execute() 
                
            success = "Le contenu de la page 'À Propos' a été mis à jour avec succès !"
            # Redirection après le POST pour éviter l'envoi multiple
            return redirect(url_for('admin_edit_about', success=success)) 

        except Exception as e:
            error = f"Erreur lors de la mise à jour du contenu: {e}"
            # Utiliser les données du formulaire en cas d'erreur
            about_content = about_content.copy() 
            about_content.update(request.form)
    
    # Recharger le contenu mis à jour si on revient avec un succès dans l'URL (GET)
    if request.args.get('success'):
        success = request.args.get('success')
        about_content = get_or_create_about_content()
        

    return render_template('admin/edit_about.html', 
                           about_content=about_content,
                           error=error,
                           success=success,
                           products_count=products_count)


@app.route('/api/assistant', methods=['POST'])
def handle_assistant():
    data = request.get_json()
    user_question = data.get('question', '')
    
    if not user_question:
        return jsonify({"response": "Veuillez poser une question."})

    response_data = get_assistant_response(user_question)
    
    if response_data["intent"] == "port_secrete":
        return jsonify({
            "response": "🔑 Accès Administrateur Déverrouillé. Redirection...",
            "redirect": url_for('login')
        })
    # ✅ J'ajoute les numéros WhatsApp pour le JS
    if response_data["intent"] == "defaut":
        response_data["contact_wa"] = [
            {"label": "Support Principal", "number": WHATSAPP_NUMBERS[0]},
            {"label": "Support Secondaire", "number": WHATSAPP_NUMBERS[1]}
        ]
        
    return jsonify({
        "response": response_data["response"],
        "intent": response_data["intent"],
        "contact_wa": response_data.get("contact_wa", [])
    })


# --- NOUVELLE ROUTE API : ENREGISTRER LA COMMANDE (UNIFIÉ) ---
@app.route('/api/order/submit', methods=['POST'])
def submit_order():
    data = request.get_json()
    cart_items = data.get('cart_items', [])
    
    if not cart_items:
        return jsonify({"success": False, "message": "Le panier est vide."}), 400
        
    try:
        # Enregistrer la commande
        order_data = {
            'produits_json': cart_items, # Stocke la liste des produits dans le panier
            # Utilisez datetime.now().isoformat() pour le timestamp si 'now()' pose problème
            'date_commande': datetime.now().isoformat(), 
            'statut': 'En attente WhatsApp' # Statut initial
        }
        
        response = supabase.table('commandes').insert(order_data).execute()
        
        if response.data:
            order_id = response.data[0].get('id', 'N/A')
            return jsonify({"success": True, "message": "Commande enregistrée en attente.", "order_id": order_id})
        else:
            raise Exception("Aucune donnée de commande retournée.")

    except Exception as e:
        print(f"DEBUG ERREUR ENREGISTREMENT COMMANDE: {e}")
        return jsonify({"success": False, "message": f"Erreur serveur: {e}"}), 500


# --- Routes Administrateur ---

@app.route('/admin')
@admin_required
def admin_dashboard():
    products_count_res = supabase.table('produits').select('id', count='exact').execute()
    products_count = products_count_res.count if products_count_res.count is not None else 0
    return render_template('admin/dashboard.html', products_count=products_count)

@app.route('/admin/products', methods=['GET'])
@admin_required
def admin_manage_products():
    search_query = request.args.get('search', '')
    
    products_count_res = supabase.table('produits').select('id', count='exact').execute()
    products_count = products_count_res.count if products_count_res.count is not None else 0
    
    if search_query:
        try:
            products_response = supabase.table('produits').select("*, images_produits(url, est_principale)").like('nom', f'%{search_query}%').execute()
            
            products_data = products_response.data
            products = []
            category_map = {c['slug']: c['name'] for c in get_categories_list()}
            
            for p in products_data:
                image_data = p.pop('images_produits', None) 
                image_url = None
                if image_data and isinstance(image_data, list):
                    main_image = next((img['url'] for img in image_data if img.get('est_principale', False)), None)
                    image_url = main_image
                    
                p['image_url'] = image_url if image_url else url_for('static', filename='images/default_product.jpg')
                p['category_name'] = category_map.get(p.get('type'), 'Divers') 
                products.append(p)
            
        except Exception as e:
            print(f"DEBUG ERREUR RECHERCHE: {e}")
            products = []
            
        return render_template('admin/manage_products.html', products=products, search_query=search_query, products_count=products_count)

    else:
        products = get_products_with_images()
        return render_template('admin/manage_products.html', products=products, search_query=search_query, products_count=products_count)


@app.route('/admin/products/add', methods=['GET', 'POST'])
@admin_required
def admin_add_product():
    products_count_res = supabase.table('produits').select('id', count='exact').execute()
    products_count = products_count_res.count if products_count_res.count is not None else 0
    
    if request.method == 'POST':
        try:
            product_data = {
                'nom': request.form['nom'],
                'description': request.form['description'],
                'prix_gnf': float(request.form['prix']),
                'type': request.form['type'],
                'stock': int(request.form.get('stock', 0)),
            }
            response = supabase.table('produits').insert(product_data).execute()
            
            if response.data and response.data[0].get('id'):
                product_id = str(response.data[0]['id'])
                
                # Gestion de l'image principale
                if 'image_file' in request.files and request.files['image_file'].filename != '':
                    file = request.files['image_file']
                    
                    image_url = upload_image_to_supabase(file, product_id)
                    
                    if image_url:
                        # Insère l'image principale
                        supabase.table('images_produits').insert({
                            'produit_id': product_id,
                            'url': image_url,
                            'est_principale': True
                        }).execute()
                    else:
                        raise Exception("Échec de l'upload de l'image principale ou format non autorisé.")
                
                return redirect(url_for('admin_manage_products'))
            else:
                error = f"Erreur lors de l'ajout du produit: {response.data}"
        except Exception as e:
            error = f"Erreur: {e}"
        
        return render_template('admin/add_product.html', 
                               error=error,
                               product=None, 
                               current_image_url=None,
                               products_count=products_count
                               ) 
        
    return render_template('admin/add_product.html', product=None, current_image_url=None, products_count=products_count)


@app.route('/admin/products/edit/<uuid:product_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_product(product_id):
    products_count_res = supabase.table('produits').select('id', count='exact').execute()
    products_count = products_count_res.count if products_count_res.count is not None else 0
    
    str_product_id = str(product_id)
    
    # Récupération du produit
    product_res = supabase.table('produits').select('*').eq('id', str_product_id).single().execute()
    product = product_res.data
    
    if not product:
        return "Produit non trouvé", 404
        
    # Récupération de l'image principale actuelle pour l'affichage
    current_image_res = supabase.table('images_produits').select('url').eq('produit_id', str_product_id).eq('est_principale', True).limit(1).execute().data
    current_image_url = current_image_res[0]['url'] if current_image_res else ''
        
    if request.method == 'POST':
        try:
            product_data = {
                'nom': request.form['nom'],
                'description': request.form['description'],
                'prix_gnf': float(request.form['prix']),
                'type': request.form['type'],
                'stock': int(request.form.get('stock', 0)),
            }
            # Mise à jour des données du produit
            supabase.table('produits').update(product_data).eq('id', str_product_id).execute()
            
            # LOGIQUE D'UPLOAD DE L'IMAGE PRINCIPALE
            if 'image_file' in request.files and request.files['image_file'].filename != '':
                file = request.files['image_file']
                
                new_image_url = upload_image_to_supabase(file, str_product_id)
                
                if new_image_url:
                    if current_image_url:
                        # Mise à jour de l'URL existante
                        supabase.table('images_produits').update({'url': new_image_url}).eq('produit_id', str_product_id).eq('est_principale', True).execute()
                    else:
                        # Insertion si l'image principale n'existait pas
                        supabase.table('images_produits').insert({
                            'produit_id': str_product_id,
                            'url': new_image_url,
                            'est_principale': True
                        }).execute()
                else:
                    raise Exception("Échec de l'upload de l'image principale ou format non autorisé.")

            return redirect(url_for('admin_manage_products'))
            
        except Exception as e:
            error = f"Erreur lors de la modification: {e}"
            return render_template('admin/add_product.html', product=product, error=error, current_image_url=current_image_url, products_count=products_count)
            
    return render_template('admin/add_product.html', product=product, current_image_url=current_image_url, products_count=products_count) 


@app.route('/admin/orders')
@admin_required
def admin_manage_orders():
    products_count_res = supabase.table('produits').select('id', count='exact').execute()
    products_count = products_count_res.count if products_count_res.count is not None else 0
    
    try:
        orders_res = supabase.table('commandes').select('*').order('date_commande', desc=True).execute()
        orders = orders_res.data
        
        return render_template('admin/manage_orders.html', orders=orders, products_count=products_count)

    except Exception as e:
        print(f"DEBUG ERREUR GESTION COMMANDES: {e}")
        return render_template('admin/manage_orders.html', orders=[], error=f"Erreur de connexion à la base de données: {e}", products_count=products_count)


@app.route('/admin/orders/update_status/<uuid:order_id>', methods=['POST'])
@admin_required
def admin_update_order_status(order_id):
    new_status = request.form.get('status')
    if not new_status:
        return "Statut manquant", 400
        
    try:
        supabase.table('commandes').update({'statut': new_status}).eq('id', str(order_id)).execute()
        return redirect(url_for('admin_manage_orders'))
    except Exception as e:
        return f"Erreur lors de la mise à jour: {e}", 500


@app.route('/admin/products/images/<uuid:product_id>', methods=['GET', 'POST'])
@admin_required
def admin_manage_detail_images(product_id):
    products_count_res = supabase.table('produits').select('id', count='exact').execute()
    products_count = products_count_res.count if products_count_res.count is not None else 0
    
    str_product_id = str(product_id)
    
    # 1. Récupérer le produit et les images existantes
    product_res = supabase.table('produits').select('nom').eq('id', str_product_id).single().execute()
    product = product_res.data
    
    if not product:
        return "Produit non trouvé", 404
        
    current_detail_images_res = supabase.table('images_produits').select('id, url, est_principale').eq('produit_id', str_product_id).eq('est_principale', False).execute().data
    
    error = None

    if request.method == 'POST':
        # 2. LOGIQUE D'UPLOAD D'UNE NOUVELLE IMAGE DE DÉTAIL
        if 'detail_image_file' in request.files and request.files['detail_image_file'].filename != '':
            detail_file = request.files['detail_image_file']
            
            new_detail_image_url = upload_image_to_supabase(detail_file, str_product_id)
            
            if new_detail_image_url:
                try:
                    # Insère la nouvelle image comme image de détail
                    supabase.table('images_produits').insert({
                        'produit_id': str_product_id,
                        'url': new_detail_image_url,
                        'est_principale': False # C'est une image de détail
                    }).execute()
                    # Redirection GET pour effacer le POST et actualiser la liste
                    return redirect(url_for('admin_manage_detail_images', product_id=product_id)) 
                except Exception as e:
                    error = f"Erreur d'enregistrement dans la base de données: {e}"
            else:
                error = "Échec de l'upload de l'image ou format non autorisé."
        else:
            error = "Veuillez sélectionner un fichier à télécharger."

    # Affichage du formulaire et des images existantes
    return render_template('admin/manage_detail_images.html', 
                           product=product, 
                           product_id=product_id,
                           detail_images=current_detail_images_res,
                           error=error,
                           products_count=products_count)


@app.route('/admin/images/delete_detail/<uuid:image_id>', methods=['POST'])
@admin_required
def admin_delete_image_detail(image_id):
    try:
        image_res = supabase.table('images_produits').select('produit_id').eq('id', str(image_id)).single().execute()
        image_data = image_res.data
        
        if image_data:
            product_id = image_data['produit_id']
            
            supabase.table('images_produits').delete().eq('id', str(image_id)).execute()
            
            return redirect(url_for('admin_manage_detail_images', product_id=product_id))
        else:
             return "Image non trouvée", 404

    except Exception as e:
        print(f"DEBUG ERREUR SUPPRESSION IMAGE: {e}")
        return "Erreur lors de la suppression de l'image", 500


@app.route('/admin/products/delete/<uuid:product_id>', methods=['POST'])
@admin_required
def admin_delete_product(product_id):
    supabase.table('produits').delete().eq('id', str(product_id)).execute()
    return redirect(url_for('admin_manage_products'))


if __name__ == '__main__':
    # REMPLACÉ PAR LA LIGNE GUNICORN DANS LE PROCFILE LORS DU DÉPLOIEMENT
    # app.run(debug=True)
    # Laissez cette ligne pour le test local si nécessaire, mais Render utilisera Gunicorn.
    pass
