from flask import Flask , jsonify, request, Response
import mysql.connector
from mysql.connector import errorcode, Error
import requests
from datetime import datetime, date
from collections import OrderedDict
import json
from config import db_config

app = Flask(__name__)

def getConnexion():
    return mysql.connector.connect(
        host=db_config["host"],
        user=db_config["user"],
        password=db_config["password"],
        database=db_config["database"]
    )
def test_connexion():
    connexion = getConnexion()
    if connexion.is_connected():
       print("Connected to MySQL database") 
    return connexion

@app.route('/GetCompanies', methods=['GET'])
def getCompanies():
    sort_order = request.args.get('sort_order')
    
    connexion = test_connexion()
    cursor = connexion.cursor()
    cursor.execute("SELECT valeur FROM config WHERE cle = 'selected_company'")
    selected_company_row = cursor.fetchone()
    selected_company = int(selected_company_row[0]) if selected_company_row else None

    base_query = "SELECT * FROM companies"
    params = []
    if sort_order:
        if sort_order.lower() == 'desc':
            base_query += " ORDER BY nom DESC"
        elif sort_order.lower() == 'asc':
            base_query += " ORDER BY nom ASC"

    cursor.execute(base_query, tuple(params))
    rows = cursor.fetchall()

    companies = []
    for row in rows:
        company = {
            'id': row[0],
            'nom': row[1]
        }
        companies.append(company)

    cursor.close()
    connexion.close()
    return jsonify({
        'data': {
            'selectedCompany': selected_company,
            'companies': companies
        }
    })


@app.route('/GetUsers/<int:company_id>', methods=["GET"]) # tri : nom prenom et email
def getUsers(company_id):
    nom = request.args.get("nom")
    prenom = request.args.get("prenom")
    email = request.args.get("email")
    status = request.args.get("status")
    sort_by = request.args.get('sort_by')
    sort_order = request.args.get('sort_order', 'asc')

    connexion = getConnexion()
    cursor = connexion.cursor()

    query = """
        SELECT u.*, c.nom as company_name
        FROM utilisateur u
        JOIN companies c 
        ON JSON_CONTAINS(u.access, JSON_OBJECT('company', c.nom), '$')
        WHERE c.id = %s
    """
    filtres = []
    params = [company_id]
    if nom:
        filtres.append("u.nom LIKE %s")
        params.append(nom + '%')
    if prenom:
        filtres.append("u.prenom LIKE %s")
        params.append(prenom + '%')
    if email:
        filtres.append("u.email = %s")
        params.append(email)
    if filtres:
        query += " AND " + " AND ".join(filtres)
    if sort_by:
        if sort_order.lower() == "desc":
            query += f" ORDER BY u.{sort_by} DESC"
        else:
            query += f" ORDER BY u.{sort_by} ASC"
    print(query)
    print(params)
    cursor.execute(query, tuple(params))
    rows = cursor.fetchall()
    users = []
    for row in rows:
        access_data = json.loads(row[4])  
        company_name = row[-1]  
        
        user = {
            'id': row[0],
            'nom': row[1],
            'prenom': row[2],
            #'type_user': row[3],
            'email': row[3],
            #'access': access_data
        }
        
        """user_found = False
        for a in access_data:
            if a["company"] == company_name:  
                if not status or (status.lower() in a["status"].lower()):
                    user_found = True
                    break
        
        if user_found:
            users.append(user)"""
        filtered_access = next((a for a in access_data if a["company"] == company_name), None)
        
        if filtered_access:
            if not status or (status.lower() in filtered_access["status"].lower()):
                user['rwaccess'] = filtered_access["rwaccess"]
                user['type_user'] = filtered_access["type_user"]
                users.append(user)

    cursor.close()
    connexion.close()

    json_response = json.dumps(users, ensure_ascii=False, indent=4)
    return Response(json_response, mimetype='application/json'), 200

@app.route('/AddUser', methods=["POST"])
def addUser():
    data = request.json
    nom = data.get('nom','').strip()
    prenom = data.get('prenom','').strip()
    email = data.get('email','').strip()
    access = data.get('access')

    if not nom or not prenom or not email or not access:
        return jsonify({"error" : "Tous les champs sont obligatoires"}),400
    
    
    access_json = json.dumps(access)

    connexion = getConnexion() 
    cursor = connexion.cursor()

    query = """
    insert into utilisateur (nom, prenom,  email, access)
    values (%s, %s, %s, %s)
    """
    params = (nom, prenom, email, access_json)
    try:
        cursor.execute(query, params)
        connexion.commit()
        new_user_id = cursor.lastrowid
    except Exception as e:
        connexion.rollback()
        return jsonify({"error": str(e)}),500
    finally:
        cursor.close()
        connexion.close()
    return jsonify({"message" : "Utilisateur ajouté", "user_id": new_user_id}),201

@app.route('/UpdateUser/<int:user_id>', methods=["PUT"])
def updateUser(user_id):
    data = request.json
    nom = data.get('nom','').strip()
    prenom = data.get('prenom','').strip()
    email = data.get('email','').strip()
    access = data.get('access')
    connexion = getConnexion()
    cursor = connexion.cursor()
    cursor.execute("SELECT * FROM utilisateur WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    if not user:
        return jsonify({"error": "Utilisateur non trouvé"}), 404
    update_fields = []
    params = []

    if nom:
        update_fields.append("nom = %s")
        params.append(nom)
    if prenom:
        update_fields.append("prenom = %s")
        params.append(prenom)
    if email:
        update_fields.append("email = %s")
        params.append(email)
    if access:
        access_json = json.dumps(access)
        update_fields.append("access = %s")
        params.append(access_json)
    
    if not update_fields:
        return jsonify({"error": "Aucune donnée à mettre à jour"}), 400

    query = "UPDATE utilisateur SET " + ", ".join(update_fields) + " WHERE id = %s"
    params.append(user_id)
    
    try:
        cursor.execute(query, params)
        connexion.commit()
    except Exception as e:
        connexion.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        connexion.close()
    
    return jsonify({"message": "Utilisateur mis à jour avec succès"}), 200

@app.route('/DeleteUser/<int:user_id>', methods=['DELETE'])
def deleteUser(user_id):
    connexion = getConnexion()
    cursor = connexion.cursor()
    cursor.execute("SELECT * FROM utilisateur WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    if not user:
        return jsonify({"error": "Utilisateur non trouvé"}), 404
    query = "DELETE FROM utilisateur WHERE id = %s"
    
    try:
        cursor.execute(query, (user_id,))
        connexion.commit()
    except Exception as e:
        connexion.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        connexion.close()
    
    return jsonify({"message": "Utilisateur supprimé avec succès"}), 200

@app.route('/GetUserDetails/<int:user_id>', methods=["GET"])
def getUserDetails(user_id):
    try:
        connexion = getConnexion()
        cursor = connexion.cursor()
        query = "SELECT id, nom, prenom, email, access FROM utilisateur WHERE id = %s"
        cursor.execute(query, (user_id,))
        user = cursor.fetchone()
        if user:
            user_details = {
                "id": user[0],
                "nom": user[1],
                "prenom": user[2],
                "email": user[3],
                "access": json.loads(user[4]) 
            }
            json_response = json.dumps(user_details, ensure_ascii=False, indent=4)
            return Response(json_response, mimetype='application/json'), 200
        else:
            return jsonify({"message": "Utilisateur non trouvé"}), 404
    
    except Exception as e:
        return jsonify({"message": str(e)}), 500
    finally:
        cursor.close()
        connexion.close()


############## API Clients #############


@app.route('/GetSecteurs', methods=['GET'])  
def getSecteurs():
    sort_order = request.args.get('sort_order')
    connexion = test_connexion()
    cursor = connexion.cursor()
    
    base_query = "SELECT * FROM secteur"
    params = []
    if sort_order:
        if sort_order.lower() == 'desc':
            base_query += " ORDER BY nom DESC"
        elif sort_order.lower() == 'asc':
            base_query += " ORDER BY nom ASC"
    
    cursor.execute(base_query, tuple(params))
    
    rows = cursor.fetchall()
    secteurs = [{'id': row[0], 'nom': row[1]} for row in rows]
    
    cursor.close()
    connexion.close()
    return jsonify(secteurs)


@app.route('/GetClients/<int:company_id>', methods=['GET'])
def getClients(company_id):
    try:
        # Récupérer les paramètres de requête
        reference = request.args.get('reference')
        raison_sociale = request.args.get('raison_sociale')
        statut = request.args.get('statut')
        email = request.args.get('email')
        telephone = request.args.get('telephone')
        date_min = request.args.get("date_min")
        date_max = request.args.get('date_max')
        evaluation_min = request.args.get('evaluation_min')
        evaluation_max = request.args.get('evaluation_max')
        secteur = request.args.get('secteur')
        ville = request.args.get('ville')
        contact_nom = request.args.get('contact_nom')
        contact_prenom = request.args.get('contact_prenom')
        sort_by = request.args.get('sort_by')
        sort_order = request.args.get('sort_order', 'asc')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

        connexion = getConnexion()  # Fonction à définir pour obtenir la connexion
        cursor = connexion.cursor()

        query = """
        SELECT c.id, c.reference, c.raison_sociale, c.statut, c.email, c.telephone,
               c.date_derniere_commande, c.evaluation, c.ville,
               GROUP_CONCAT(s.nom SEPARATOR ', ') AS secteurs
        FROM clients c
        LEFT JOIN client_secteur cs ON c.id = cs.client_id
        LEFT JOIN secteur s ON cs.secteur_id = s.id
        JOIN companies comp ON c.company_id = comp.id
        LEFT JOIN contacts ct ON ct.client_id = c.id
        WHERE comp.id = %s
        """

        params = [company_id]

        # Ajout des filtres
        if reference:
            query += " AND c.reference = %s"
            params.append(reference)
        if raison_sociale:
            query += " AND c.raison_sociale LIKE %s"
            params.append(raison_sociale + '%')
        if statut:
            query += " AND c.statut like %s"
            params.append(statut + '%')
        if email:
            query += " AND c.email = %s"
            params.append(email)
        if telephone:
            query += " AND (c.telephone = %s OR c.mobile = %s OR ct.telephone = %s OR ct.mobile = %s)"
            params.extend([telephone, telephone, telephone, telephone])
        if date_min:
            try:
                date_obj = datetime.strptime(date_min, '%d/%m/%Y').date()
                query += " AND c.date_derniere_commande >= %s"
                params.append(date_obj)
            except ValueError:
                return jsonify({"error": "Invalid date format. Use dd/mm/yyyy."}), 400
        if date_max:
            try:
                date_obj = datetime.strptime(date_max, '%d/%m/%Y').date()
                query += " AND c.date_derniere_commande <= %s"
                params.append(date_obj)
            except ValueError:
                return jsonify({"error": "Invalid date format. Use dd/mm/yyyy."}), 400
        if evaluation_min:
            query += " AND c.evaluation >= %s"
            params.append(evaluation_min)
        if evaluation_max:
            query += " AND c.evaluation <= %s"
            params.append(evaluation_max)
        if ville:
            query += " AND c.ville LIKE %s"
            params.append(ville + '%')
        if secteur:
            query += """
            AND c.id IN (
                SELECT client_id FROM client_secteur cs
                JOIN secteur s ON cs.secteur_id = s.id
                WHERE s.nom = %s
            )
            """
            params.append(secteur)
        if contact_nom:
            query += " AND ct.nom LIKE %s"
            params.append(contact_nom + '%')
        if contact_prenom:
            query += " AND ct.prenom LIKE %s"
            params.append(contact_prenom + '%')

        # Ajout de GROUP BY pour chaque client
        query += " GROUP BY c.id"

        # Liste sécurisée des colonnes pour `sort_by`, basée sur les champs filtrés
        valid_columns = ['reference', 'raison_sociale', 'statut', 'email', 'telephone', 'date_derniere_commande', 'evaluation', 'ville']

        # Vérification si `sort_by` est valide
        if sort_by and sort_by in valid_columns:
            query += " ORDER BY c." + sort_by + " " + ('DESC' if sort_order.lower() == 'desc' else 'ASC')

        # Calcul de l'offset pour la pagination
        offset = (page - 1) * per_page
        query += " LIMIT %s OFFSET %s"
        params.extend([per_page, offset])

        print("Query:", query)
        print("Parameters:", params)

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()

        clients = []
        for row in rows:
            client = {
                'id': row[0],
                'reference': row[1],
                'raison_sociale': row[2],
                'statut': row[3],
                'email': row[4],
                'telephone': row[5],
                'date_derniere_commande': row[6].strftime('%d/%m/%Y') if row[6] else None,
                'evaluation': row[7],
                'ville': row[8],
                'secteurs': row[9].split(', ') if row[9] else []  # Convertir la chaîne en liste
            }
            clients.append(client)

        cursor.close()

        return jsonify({
            'page': page,
            'per_page': per_page,
            'total_clients': len(clients),
            'clients': clients
        })

    except Exception as e:
        return Response(json.dumps({'error': str(e)}), mimetype='application/json'), 500


@app.route('/GetClientDetails/<int:company_id>/<int:client_id>', methods=['GET'])
def getClientDetails(company_id, client_id):
    try:
        connexion = getConnexion()
        cursor = connexion.cursor()
        
        # Récupérer les détails du client
        query = """
        SELECT c.reference, c.raison_sociale, c.statut, c.email, c.telephone, c.mobile, 
               c.site_web, c.date_derniere_commande, c.evaluation, c.adresse, c.ville, 
               c.info_personnelles, c.preference, c.decision, c.raison, 
               c.position_fiscale, c.n_tva, c.nature_paiement, c.delai_paiement, c.methode_livraison
        FROM clients c
        JOIN companies comp ON c.company_id = comp.id
        WHERE c.id = %s AND comp.id = %s
        """
        cursor.execute(query, (client_id, company_id))
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "client not found"}), 404

        client = {
            'reference': row[0],
            'raison_sociale': row[1],
            'statut': row[2],
            'email': row[3],
            'telephone': row[4],
            'mobile': row[5],
            'site_web': row[6],
            'date_derniere_commande': row[7].strftime('%d/%m/%Y') if row[7] else None,
            'evaluation': row[8],
            'adresse': row[9],
            'ville': row[10],
            'info_personnelles': row[11],
            'preference': row[12],
            'decision': row[13],
            'raison': row[14],
            
            'position_fiscale': row[15],
            'n_tva': row[16],
            'nature_paiement': row[17],
            'delai_paiement': row[18],
            'methode_livraison' : row[19]
        }

        # Récupérer les secteurs du client
        query_secteurs = """
        SELECT s.nom
        FROM client_secteur cs
        JOIN secteur s ON cs.secteur_id = s.id
        WHERE cs.client_id = %s
        """
        cursor.execute(query_secteurs, (client_id,))
        secteurs_rows = cursor.fetchall()
        secteurs = [row[0] for row in secteurs_rows]  # Liste des secteurs
        client['secteurs'] = secteurs

        # Récupérer les contacts associés au client
        query_contact = """
        SELECT id, nom, prenom, telephone, mobile, email, poste, notes 
        FROM contacts
        WHERE client_id = %s
        """
        cursor.execute(query_contact, (client_id,))
        contacts_rows = cursor.fetchall()
        contacts = []
        for row in contacts_rows:
            contact = {
                'id': row[0],
                'nom': row[1],
                'prenom': row[2],
                'telephone': row[3],
                'mobile': row[4],
                'email': row[5],
                'poste': row[6],
                'notes': row[7]
            }
            contacts.append(contact)
        client['contacts'] = contacts

        json_response = json.dumps(client, ensure_ascii=False, indent=4)
        return Response(json_response, mimetype='application/json'), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 500

    finally:
        cursor.close()
        connexion.close()

@app.route('/UpdateClient/<int:client_id>', methods=['PUT'])
def updateClient(client_id):
    try:
        data = request.json
        
        # Définir les champs modifiables et les valeurs autorisées pour le statut
        modifiable_fields = ['statut', 'evaluation', 'raison', 'info_personnelles', 'preference', 'decision']
        valid_statuses = ['risqué', 'modéré', 'fiable']
        
        # Vérifier si tous les champs dans la demande sont modifiables
        for field in data.keys():
            if field not in modifiable_fields:
                return jsonify({"error": f"Le champ '{field}' n'est pas modifiable."}), 400
        
        # Vérifier la validité du champ statut (insensible à la casse)
        if 'statut' in data and data['statut'].lower() not in valid_statuses:
            return jsonify({"error": "Le champ 'statut' doit être l'un des suivants : 'risqué', 'modéré', 'fiable'."}), 400
        
        # Vérifier si le client existe
        connexion = getConnexion()
        cursor = connexion.cursor()
        cursor.execute("SELECT COUNT(*) FROM clients WHERE id = %s", (client_id,))
        client_exists = cursor.fetchone()[0] > 0

        if not client_exists:
            return jsonify({"error": "Client not found."}), 404
        
        updates = []
        params = []

        # Ajouter les champs modifiables à la liste des mises à jour
        for field in modifiable_fields:
            if field in data:
                updates.append(f"{field} = %s")
                params.append(data[field])

        # Si aucun champ modifiable n'est fourni, renvoyer une erreur
        if not updates:
            return jsonify({"error": "Aucun champ modifiable fourni."}), 400

        # Construire la requête de mise à jour
        query = f"""
        UPDATE clients SET 
            {', '.join(updates)}
        WHERE id = %s
        """
        
        params.append(client_id)

        # Exécuter la requête de mise à jour
        cursor.execute(query, params)
        connexion.commit()
        cursor.close()
        
        return jsonify({"message": "Client updated successfully."}), 200

    except Exception as e:
        return Response(json.dumps({'error': str(e)}), mimetype='application/json'), 500
    
###################  API pour les commandes  #####################

@app.route('/GetOrders/<int:client_id>', methods=['GET'])
def GetOrders(client_id):
    try:
        connexion = getConnexion()
        cursor = connexion.cursor()

        numero = request.args.get("numero")
        date_min = request.args.get("date_min")
        date_max = request.args.get("date_max")
        montant_min = request.args.get("montant_min")
        montant_max = request.args.get("montant_max")
        date_livraison_min = request.args.get("date_livraison_min")
        date_livraison_max = request.args.get("date_livraison_max")
        etat_facture = request.args.get("etat_facture")
        etat_livraison = request.args.get("etat_livraison")
        sort_by = request.args.get('sort_by')
        sort_order = request.args.get('sort_order', 'asc')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 2))
        offset = (page - 1) * limit

        query = """
        SELECT c.id, c.numero, c.date_commande, c.montant, c.date_livraison, c.etat_facture, c.etat_livraison
        FROM commande c 
        JOIN clients cl ON c.ref_client = cl.id
        WHERE c.ref_client = %s
        """
        params = [client_id]

        if numero:
            query += " AND c.numero = %s"
            params.append(numero)
        if date_min:
            try:
                date_obj = datetime.strptime(date_min, '%d/%m/%Y').date()
                query += " AND c.date_commande >= %s"
                params.append(date_obj)
            except ValueError:
                return jsonify({"error": "Invalid date format. Use dd/mm/yyyy."}), 400
        if date_max:
            try:
                date_obj = datetime.strptime(date_max, '%d/%m/%Y').date()
                query += " AND c.date_commande <= %s"
                params.append(date_obj)
            except ValueError:
                return jsonify({"error": "Invalid date format. Use dd/mm/yyyy."}), 400
        if date_livraison_min:
            try:
                date_obj = datetime.strptime(date_livraison_min, '%d/%m/%Y').date()
                query += " AND c.date_livraison >= %s"
                params.append(date_obj)
            except ValueError:
                return jsonify({"error": "Invalid date format. Use dd/mm/yyyy."}), 400
        if date_livraison_max:
            try:
                date_obj = datetime.strptime(date_livraison_max, '%d/%m/%Y').date()
                query += " AND c.date_livraison <= %s"
                params.append(date_obj)
            except ValueError:
                return jsonify({"error": "Invalid date format. Use dd/mm/yyyy."}), 400
        if montant_min:
            query += " AND c.montant >= %s"
            params.append(montant_min)
        if montant_max:
            query += " AND c.montant <= %s"
            params.append(montant_max)
        if etat_facture:
            query += " AND c.etat_facture = %s"
            params.append(etat_facture)
        if etat_livraison:
            query += " AND c.etat_livraison = %s"
            params.append(etat_livraison)

        if sort_by:
            if sort_order.lower() == 'desc':
                query += f" ORDER BY c.{sort_by} DESC"
            else:
                query += f" ORDER BY c.{sort_by} ASC"
        
        query += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        orders = []
        for row in rows:
            order = {
                'id': row[0],
                'numero': row[1],
                'date_commande': row[2].strftime('%d/%m/%Y') if row[2] else None,
                'montant': row[3],
                'date_livraison': row[4].strftime('%d/%m/%Y') if row[4] else None,
                'etat_facture': row[5],
                'etat_livraison': row[6],
                'details': []
            }

            details_query = """
            SELECT a.ref_article, a.nom, ca.emballage, ca.quantite, ca.unite_mesure, ca.prix
            FROM article a
            JOIN commande_article ca ON ca.id_article = a.id
            WHERE ca.id_commande = %s
            """
            cursor.execute(details_query, [order['id']])
            details_rows = cursor.fetchall()
            for detail in details_rows:
                article = {
                    'ref_article': detail[0],
                    'article': detail[1],
                    'emballage': detail[2],
                    'quantite': detail[3],
                    'unite_mesure': detail[4],
                    'prix': detail[5]
                }
                order['details'].append(article)


            orders.append(order)

        json_response = json.dumps(orders, ensure_ascii=False, indent=4)
        return Response(json_response, mimetype='application/json'), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        connexion.close()



@app.route('/GetFinancialSituation/<int:client_id>', methods=["GET"])
def getFinancialSituation(client_id):
    try:
        connexion = getConnexion()
        cursor = connexion.cursor()
        
        query = """
        select c.reference, c.raison_sociale, c.statut, c.evaluation, s.ca_genere, s.montant_regle, s.encours,
        s.limite_credit, s.impaye, s.contentieux, s.provision_perte, s.preavis, s.lrs_recue
        FROM clients c
        JOIN situation_financiere s ON c.id = s.client_id
        WHERE s.client_id = %s
        """
        cursor.execute(query, (client_id,))
        result = cursor.fetchone()
        if result is None:
            return jsonify({"message": "Client not found"})
        
        situation_financiere = {
            "reference": result[0],
            "raison_sociale": result[1],
            "statut": result[2],
            "evaluation": result[3],
            "ca_genere": result[4],
            "montant_regle": result[5],
            "encours": result[6],
            "limite_credit": result[7],
            "impaye": result[8],
            "contentieux": result[9],
            "provision_perte": result[10],
            "preavis": result[11],
            "lrs_recue": result[12]
        }
        json_response = json.dumps(situation_financiere, ensure_ascii=False, indent=4)
        return Response(json_response, mimetype='application/json'), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

    finally:
        cursor.close()
        connexion.close()


@app.route('/GetPayments/<int:client_id>', methods = ["GET"])
def getPayments(client_id):
    try:
        connexion = getConnexion()
        cursor = connexion.cursor()

        reference = request.args.get("reference")
        montant_min = request.args.get("montant_min")
        montant_max = request.args.get("montant_max")
        date_min = request.args.get("date_min")
        date_max = request.args.get("date_max")
        methode_paiement = request.args.get("methode_paiement")
        etat = request.args.get("etat")
        sort_by = request.args.get("sort_by")
        sort_order = request.args.get('sort_order', 'asc')
        page = int(request.args.get('page', 1))  
        page_size = int(request.args.get('page_size', 2))  
        offset = (page - 1) * page_size

        query = """
        SELECT p.id, p.date_paiement, p.reference, p.montant, p.methode_paiement, p.etat
        FROM paiement p 
        WHERE p.client_id = %s
        """
        params = [client_id]

        if reference:
            query += " AND p.reference = %s"
            params.append(reference)
        if montant_min:
            query += " AND p.montant >= %s"
            params.append(montant_min)
        if montant_max:
            query += " AND p.montant <= %s"
            params.append(montant_max)
        if date_min:
            try:
                date_obj = datetime.strptime(date_min, '%d/%m/%Y').date()
                query += " AND p.date_paiement >= %s"
                params.append(date_obj)
            except ValueError:
                return jsonify({"error": "Invalid date format. Use dd/mm/yyyy."}), 400
        if date_max:
            try:
                date_obj = datetime.strptime(date_max, '%d/%m/%Y').date()
                query += " AND p.date_paiement <= %s"
                params.append(date_obj)
            except ValueError:
                return jsonify({"error": "Invalid date format. Use dd/mm/yyyy."}), 400
        if methode_paiement:
            query += " AND p.methode_paiement like %s"
            params.append(methode_paiement +'%')
        if etat:
            query += " AND p.etat like %s"
            params.append(etat +'%')

        if sort_by:
            if sort_order.lower() == 'desc':
                query += f" ORDER BY p.{sort_by} DESC"
            else:
                query += f" ORDER BY p.{sort_by} ASC"
        
        query += " LIMIT %s OFFSET %s"
        params.extend([page_size, offset])

        cursor.execute(query, tuple(params))
        result_paiements = cursor.fetchall()
        paiements = []
        for row in result_paiements:
            paiement = {
                "id": row[0],
                "date_paiement": row[1].strftime('%d/%m/%Y') if row[1] else None,
                "reference": row[2],
                "montant": row[3],
                "methode_paiement": row[4],
                "etat": row[5],
                "factures": []
            }
            query_factures = """
            SELECT f.ref
            FROM facture f
            JOIN facture_paiement fp ON f.id = fp.id_facture
            WHERE fp.id_paiement = %s
            """
            cursor.execute(query_factures, (row[0],))
            result_factures = cursor.fetchall()

            for facture_row in result_factures:
                paiement["factures"].append(facture_row[0])

            paiements.append(paiement)
        json_response = json.dumps(paiements, ensure_ascii=False, indent=4)
        return Response(json_response, mimetype='application/json'), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500

@app.route('/GetSamples/<int:client_id>', methods=["GET"])
def getSamples(client_id):
    try:
        connexion = getConnexion()
        cursor = connexion.cursor()
        sort_by = request.args.get('sort_by')
        sort_order = request.args.get('sort_order', 'asc')
        query = """
        select id, reference_nom, date_souhaitee, date_envoi, quantite, etat, note
        from echantillon
        where client_id = %s
        """
        params = [client_id]
        if sort_by:
            if sort_order.lower() == 'desc':
                query += f" ORDER BY {sort_by} DESC"
            else:
                query += f" ORDER BY {sort_by} ASC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        echantillons = []
        for row in rows:
            reference_nom = row[1]
            if '[' in reference_nom and ']' in reference_nom:
                start_idx = reference_nom.index('[') + 1
                end_idx = reference_nom.index(']')
                reference = reference_nom[start_idx:end_idx]
                nom = reference_nom.replace(f'[{reference}]', '').strip()
            else:
                reference = None
                nom = reference_nom.strip('[]')
            produit = {
                'id': row[0],
                'reference': reference,
                'nom': nom,
                'date_souhaitee':row[2].strftime('%d/%m/%Y') if row[3] else None,
                'date_envoi': row[3].strftime('%d/%m/%Y') if row[4] else None,
                'quantite': row[4],
                'etat':row[5],
                'note':row[6]
            }
            echantillons.append(produit)
        json_response = json.dumps(echantillons, ensure_ascii=False, indent=4)
        return Response(json_response, mimetype='application/json'), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500
    finally:
        cursor.close()
        connexion.close()

@app.route('/AddSample/<int:client_id>', methods=['POST'])
def addSample(client_id):
    connexion = None
    cursor = None
    try:
        data = request.get_json()

        reference_nom = data.get('reference_nom', '').strip() if data.get('reference_nom') else None
        date_souhaitee = data.get('date_souhaitee', '').strip() if data.get('date_souhaitee') else None
        date_envoi = data.get('date_envoi', '').strip() if data.get('date_envoi') else None
        quantite = data.get('quantite')
        etat = data.get('etat', '').strip() if data.get('etat') else None
        note = data.get('note', '').strip() if data.get('note') else None
#### le nom est obligatoire (pour le moment)
        if not reference_nom:
            return jsonify({"error": "Le champ 'reference_nom' est obligatoire."}), 400
        if not etat:
            return jsonify({"error": "Le champ 'etat' est obligatoire."}), 400
        if etat:
            etat = etat.strip().lower()  
            valid_etats = ['demandé', 'envoyé', 'terminé']
            if etat not in valid_etats:
                return jsonify({"error": f"L'état '{etat}' n'est pas valide. Les valeurs acceptées sont: demandé, envoyé, terminé."}), 400
        date_souhaite_obj = None
        date_envoi_obj = None
        try:
            if date_souhaitee:
                date_souhaite_obj = datetime.strptime(date_souhaitee, '%d/%m/%Y').date()
            if date_envoi:
                date_envoi_obj = datetime.strptime(date_envoi, '%d/%m/%Y').date()
        except ValueError:
            return jsonify({"error": "Invalid date format. Use dd/mm/yyyy."}), 400

        connexion = getConnexion()
        cursor = connexion.cursor()

        query = """
            INSERT INTO echantillon (reference_nom,  date_souhaitee, date_envoi, quantite, etat, note, client_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        params = (reference_nom, date_souhaite_obj, date_envoi_obj, quantite, etat, note, client_id)
        cursor.execute(query, params)
        connexion.commit()

        echantillon_id = cursor.lastrowid

        cursor.close()
        connexion.close()

        return jsonify({
            "message": "Echantillon ajouté avec succès",
            "echantillon_id": echantillon_id
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}),500
    finally:
        if cursor:
            cursor.close()
        if connexion:
            connexion.close()  


@app.route('/DeleteSample/<int:client_id>/<int:sample_id>', methods=['DELETE'])
def deleteSample(client_id, sample_id):
    connexion = None
    cursor = None
    try:
        connexion = getConnexion()
        cursor = connexion.cursor()
        cursor.execute("SELECT * FROM echantillon WHERE id = %s AND client_id = %s", (sample_id, client_id))
        echantillon = cursor.fetchone()

        if not echantillon:
            return jsonify({"error": "L'échantillon avec cet ID pour ce client n'existe pas."}), 404

        query = "delete from echantillon where id = %s AND client_id = %s"
        cursor.execute(query, (sample_id, client_id))
        connexion.commit()

        return jsonify({
            "message": "Échantillon supprimé avec succès",
            "sample_id": sample_id,
            "client_id": client_id
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connexion:
            connexion.close()

@app.route('/UpdateSample/<int:client_id>/<int:sample_id>', methods = ["PUT"])
def updateSample(client_id, sample_id):
   
    data = request.json
    reference_nom = data.get('reference_nom', '').strip()
    date_souhaitee = data.get('date_souhaitee', '').strip()
    date_envoi = data.get('date_envoi', '').strip()
    quantite = data.get('quantite')
    etat = data.get('etat', '').strip()
    note = data.get('note', '').strip()
    
    # Convertir les dates au format yyyy-mm-dd pour être compatibles avec SQL
    def convert_to_date(date_str):
        if date_str:
            try:
                return datetime.strptime(date_str, '%d/%m/%Y').strftime('%Y-%m-%d')
            except ValueError:
                return None
        return None

    # Appeler la fonction de conversion pour les dates
    date_souhaitee_db = convert_to_date(date_souhaitee)
    date_envoi_db = convert_to_date(date_envoi)
    
    # Si les dates ne sont pas valides, renvoyer une erreur
    if (date_souhaitee and not date_souhaitee_db) or (date_envoi and not date_envoi_db):
        return jsonify({"error": "Format de date invalide, veuillez utiliser dd/mm/yyyy"}), 400
    
    connexion = getConnexion()
    cursor = connexion.cursor()
    cursor.execute("select * from echantillon where id = %s and client_id = %s", (sample_id, client_id))
    echantillon = cursor.fetchone()
    if not echantillon:
        return jsonify({"error": "Echantillon non trouvé"}), 404
    
    update_fields = []
    params = []
    
    if reference_nom:
        update_fields.append("reference_nom = %s")
        params.append(reference_nom)
    if date_souhaitee_db:
        update_fields.append("date_souhaitee = %s")
        params.append(date_souhaitee_db)
    if date_envoi_db:
        update_fields.append("date_envoi = %s")
        params.append(date_envoi_db)
    if quantite is not None:
        update_fields.append("quantite = %s")
        params.append(quantite)
    if etat:
        update_fields.append("etat = %s")
        params.append(etat)
    if note:
        update_fields.append("note = %s")
        params.append(note)

    if not update_fields:
        return jsonify({"error": "Aucune donnée à mettre à jour"}), 400

    query = "update echantillon set " + ", ".join(update_fields) + " WHERE id = %s AND client_id = %s"
    params.extend([sample_id, client_id])
    
    try:
        cursor.execute(query, params)
        connexion.commit()
    except Exception as e:
        connexion.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        connexion.close()
    
    return jsonify({"message": "Echantillon mis à jour avec succès"}), 200


### API pour relation client
@app.route('/GetRecords/<int:client_id>', methods= ["GET"])
def getRecords(client_id):
    try:
        date_min = request.args.get("date_min")
        date_max = request.args.get("date_max")
        nom = request.args.get("nom")
        prenom = request.args.get("prenom")
        favori = request.args.get("favori")
        important = request.args.get("important")
        connexion = getConnexion()
        cursor = connexion.cursor()
        query = """
        select * from records where client_id = %s
        """
        params = [client_id]
        if date_min:
            try:
                date_obj = datetime.strptime(date_min, '%d/%m/%Y').date()
                query += " AND record_date_time >= %s"
                params.append(date_obj)
            except ValueError:
                return jsonify({"error": "Invalid date format. Use dd/mm/yyyy."}), 400
        if date_max:
            try:
                date_obj = datetime.strptime(date_max, '%d/%m/%Y').date()
                query += " AND record_date_time <= %s"
                params.append(date_obj)
            except ValueError:
                return jsonify({"error": "Invalid date format. Use dd/mm/yyyy."}), 400
        if nom:
            query += " and user_name like %s"
            params.append(nom)
        if prenom:
            query += " and prenom like %s"
            params.append(prenom)
        if favori:
            query += " and favori = %s"
            params.append(favori)
        if important:
            query += " and important = %s"
            params.append(important)
        
        cursor.execute(query, params)

        #cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        records = []
        for row in rows:
            record = {
                'record_date':row[1].strftime('%d/%m/%Y %H:%M:%S') if row[1] else None,
                'record_type': row[2],
                'nom':row[3],
                'prenom':row[4],
                'record_text': row[5],
                'favori': row[6],
                'important': row[7]
            }
            records.append(record)
            
        return jsonify(records)
    except Exception as e:
        return jsonify({"message": str(e)}), 500
    finally:
        cursor.close()
        connexion.close()



@app.route('/AddRecord/<int:client_id>', methods = ["POST"])
def addRecord(client_id):
    connexion = getConnexion()
    cursor = connexion.cursor()
    try:
        data = request.get_json()
        record_time = data.get('record_time', '').strip() if data.get('record_time') else None
        record_type = data.get('record_type', '').strip().lower() 
        nom = data.get('nom', '')
        prenom = data.get('prenom', '')
        record_text = data.get('record_text', '')
        favori = data.get('favori')
        important = data.get('important')

        valid_record_types = ["commentaire", "interaction", "action", "réclamation"]

        if record_type not in valid_record_types:
            return jsonify({"error": "record_type invalide. Les valeurs valides sont : commentaire, interaction, action, réclamation"}), 400

        if record_time:
            try:
                date_obj = datetime.strptime(record_time, '%d/%m/%Y %H:%M:%S')
                record_time = date_obj.strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                return jsonify({"error": "Le format de la date doit être dd/mm/yyyy hh:mm:ss"}), 400

        query = """
        INSERT INTO records (record_date_time, record_type, user_name, prenom, record_text, favori, important, client_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        params = (record_time, record_type, nom, prenom, record_text, favori, important, client_id)

        cursor.execute(query, params)
        connexion.commit()
        record_id = cursor.lastrowid

        return jsonify({
            "message": "record ajouté avec succès",
            "record_id": record_id
        }), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connexion:
            connexion.close()


###############"" les API pour les produits ###############"

@app.route('/GetProducts', methods = ['GET'])
def getProducts():
    try:
        reference = request.args.get('reference')
        nom = request.args.get('nom')
        date_min = request.args.get('date_min')
        date_max = request.args.get('date_max')
        quantite_min = request.args.get('quantite_min')
        quantite_max = request.args.get('quantite_max')
        secteur = request.args.get('secteur')
        sort_by = request.args.get('sort_by')
        sort_order = request.args.get('sort_order', 'asc')
        page = request.args.get('page', 1, type=int)
        limit = int(request.args.get('limit', 2))
        offset = (page - 1) * limit

        connexion = getConnexion()
        cursor = connexion.cursor()
        query = """
        select p.id, p.reference, p.nom, p.date_derniere_commande, p.quantite_stock, GROUP_CONCAT(s.nom SEPARATOR ', ') as secteurs
        from produit p 
        left join produit_secteur ps on p.id = ps.produit_id
        left join secteur s on ps.secteur_id = s.id
        """
        params = []
        conditions = []
        
        if reference:
            conditions.append("p.reference = %s")
            params.append(reference)
        if nom:
            conditions.append("p.nom LIKE %s")
            params.append(nom+'%') 
        if date_min:
            try:
                date_obj = datetime.strptime(date_min, '%d/%m/%Y').date()
                conditions.append("p.date_derniere_commande >= %s")
                params.append(date_obj)
            except ValueError:
                return jsonify({"error": "Invalid date format. Use dd/mm/yyyy."}), 400
        if date_max:
            try:
                date_obj = datetime.strptime(date_max, '%d/%m/%Y').date()
                conditions.append("p.date_derniere_commande <= %s")
                params.append(date_obj)
            except ValueError:
                return jsonify({"error": "Invalid date format. Use dd/mm/yyyy."}), 400
        if quantite_min is not None:  
            conditions.append("p.quantite_stock >= %s")
            params.append(quantite_min)
        if quantite_max is not None:  
            conditions.append("p.quantite_stock <= %s")
            params.append(quantite_max)
        if secteur:
            conditions.append("""
            p.id IN (SELECT produit_id FROM produit_secteur ps
                      JOIN secteur s ON ps.secteur_id = s.id
                      WHERE s.nom = %s)
            """)
            params.append(secteur)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += """
        GROUP BY p.id, p.reference, p.nom, p.date_derniere_commande, p.quantite_stock
        """

        if sort_by:
            order = "DESC" if sort_order.lower() == 'desc' else "ASC"
            query += f" ORDER BY p.{sort_by} {order}"
        
        query += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        produits = []
        for row in rows:
            produit = {
                'id': row[0],
                'reference': row[1],
                'nom': row[2],
                'date_derniere_commande': row[3].strftime('%d/%m/%Y') if row[3] else None,
                'quantite_stock': row[4],
                'secteur': row[5].split(', ') if row[5] else []
            }
            produits.append(produit)

        json_response = json.dumps(produits, ensure_ascii=False, indent=4)
        return Response(json_response, mimetype='application/json'), 200

    except Exception as e:
        return Response(json.dumps({'error': str(e)}), mimetype='application/json'), 500



@app.route('/GetProductDetails/<int:product_id>', methods = ["GET"])
def getProductDetails(product_id):
    try:
        sort_by = request.args.get('sort_by')
        sort_order = request.args.get('sort_order', 'asc')

        connexion = getConnexion()
        cursor = connexion.cursor()

        query = """
        select p.reference, p.nom, p.quantite_stock, p.prix_vente, p.note_commentaire
        from produit p
        where p.id = %s
        """
        cursor.execute(query, (product_id,))
        row = cursor.fetchone()

        if not row:
            return jsonify({"error": "product not found"}), 404

        product = {
            'reference': row[0],
            'nom': row[1],
            'quantite_stock': row[2],
            'prix_vente': row[3],
            'note_commentaire': row[4]
        }

        query_secteurs = """
        select s.nom from produit_secteur ps
        join secteur s on ps.secteur_id = s.id
        where ps.produit_id = %s
        """
        cursor.execute(query_secteurs, (product_id,))
        secteurs_rows = cursor.fetchall()
        secteurs = [row[0] for row in secteurs_rows]
        product['secteurs'] = secteurs

        # Définir le tri par défaut ou en fonction des paramètres
        sort_by_fields = ['valeur', 'quantite_en_stock', 'seuil', 'prix_vente_objectif', 'prix_vente_min', 'date_derniere_commande', 'date_expiration']
        if sort_by not in sort_by_fields:
            sort_by = 'valeur'  # Par défaut, trier par "valeur"
        sort_order = 'DESC' if sort_order.lower() == 'desc' else 'ASC'  # Trier en 'ASC' par défaut, sinon 'DESC' si spécifié

        # Requête pour les variantes avec tri
        query_variante = f"""
        select vp.id, v.valeur, vp.quantite_en_stock, vp.seuil, vp.prix_vente_objectif, vp.prix_vente_min,
        vp.date_derniere_commande, vp.date_expiration 
        from variantes v
        join variante_produit vp 
        on v.id = vp.variante_id
        where produit_id = %s
        ORDER BY {sort_by} {sort_order}
        """

        cursor.execute(query_variante, (product_id,))
        rows = cursor.fetchall()

        variantes = []
        for row in rows:
            variante = {
                'id': row[0],
                'valeur': row[1],
                'quantite_en_stock': row[2],
                'seuil': row[3],
                'prix_vente_objectif': row[4],
                'prix_vente_min': row[5],
                'date_derniere_commande': row[6].strftime('%d/%m/%Y') if row[6] else None,
                'date_expiration': row[7].strftime('%d/%m/%Y') if row[7] else None
            }
            variantes.append(variante)

        product['variantes'] = variantes

        # Retourner la réponse JSON
        json_response = json.dumps(product, ensure_ascii=False, indent=4)
        return Response(json_response, mimetype='application/json'), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 500

    finally:
        cursor.close()
        connexion.close()


@app.route('/UpdateProduct/<int:product_id>', methods=['PUT'])
def updateProduct(product_id):
    try:
        data = request.get_json()

        note_commentaire = data.get('note_commentaire')
        seuil = data.get('seuil')
        date_expiration = data.get('date_expiration')
        variante_id = data.get('variante_id')  

        connexion = getConnexion()
        cursor = connexion.cursor()

        if note_commentaire is not None:
            query_produit = """
            UPDATE produit
            SET note_commentaire = %s
            WHERE id = %s
            """
            cursor.execute(query_produit, (note_commentaire, product_id))

        if variante_id is not None:
            if seuil is not None:
                query_seuil = """
                UPDATE variante_produit
                SET seuil = %s
                WHERE produit_id = %s AND variante_id = %s
                """
                cursor.execute(query_seuil, (seuil, product_id, variante_id))

            if date_expiration is not None:
                try:
                    date_obj = datetime.strptime(date_expiration, '%d/%m/%Y').date()
                except ValueError:
                    return jsonify({"error": "Invalid date format. Use dd/mm/yyyy."}), 400

                query_date = """
                UPDATE variante_produit
                SET date_expiration = %s
                WHERE produit_id = %s AND variante_id = %s
                """
                cursor.execute(query_date, (date_obj, product_id, variante_id))

        connexion.commit()

        return jsonify({"message": "Product updated successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        connexion.close()

if __name__ == "__main__":
    app.run(debug=True)
