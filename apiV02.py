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

@app.route('/GetUser', methods=['POST'])
def getUser():
    data = request.get_json()
    email = data.get('email')
    if not email:
        return jsonify({"error": "Email manquant dans la requête"}), 400
    
    connexion = getConnexion()
    cursor = connexion.cursor()
    cursor.execute("SELECT nom, prenom, access FROM utilisateur WHERE email = %s", (email,))
    user_row = cursor.fetchone()

    if not user_row:
        cursor.close()
        connexion.close()
        return jsonify({"error": "Utilisateur non trouvé"}), 404

    nom = user_row[0]
    prenom = user_row[1]
    
    try:
        access_data = json.loads(user_row[2])  
    except json.JSONDecodeError:
        cursor.close()
        connexion.close()
        return jsonify({"error": "Données d'accès invalides"}), 400

    active_companies = [entry['company'] for entry in access_data if entry['status'].lower() == 'actif']

    if not active_companies:
        cursor.close()
        connexion.close()
        return jsonify({"message": "Aucune entreprise active"}), 200

    placeholders = ','.join(['%s'] * len(active_companies))
    base_query = f"SELECT id, nom FROM companies WHERE nom IN ({placeholders})"

    cursor.execute(base_query, tuple(active_companies))
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
        'user': {
            'nom': nom,
            'prenom': prenom,
            'entreprises_actives': companies
        }
    }), 200

@app.route('/GetUsers', methods=["POST"])  
def getUsers():
    data = request.get_json() 
    company_id = data.get('company_id') 
    nom = data.get("nom")
    prenom = data.get("prenom")
    email = data.get("email")
    status = data.get("status")
    sort_by = data.get('sort_by')
    sort_order = data.get('sort_order', 'asc')
    if not company_id:
        return jsonify({"error": "company_id manquant dans la requête"}), 400

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
            'email': row[3]
        }

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

@app.route('/UpdateUser', methods=["PUT"])
def updateUser():
    data = request.json
    user_id = data.get('user_id')
    nom = data.get('nom','').strip()
    prenom = data.get('prenom','').strip()
    email = data.get('email','').strip()
    access = data.get('access')
    if not user_id:
        return jsonify({"error":"user_id est obligatoire"})
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

@app.route('/DeleteUsers', methods=['DELETE'])
def deleteUsers():
    user_ids = request.json.get('user_ids', [])
    
    if not user_ids:
        return jsonify({"error": "Aucun ID d'utilisateur fourni"}), 400
    connexion = getConnexion()
    cursor = connexion.cursor()

    format_strings = ','.join(['%s'] * len(user_ids))
    cursor.execute(f"SELECT id FROM utilisateur WHERE id IN ({format_strings})", tuple(user_ids))
    found_users = cursor.fetchall()

    found_ids = [user[0] for user in found_users]
    
    if len(found_ids) != len(user_ids):
        missing_ids = set(user_ids) - set(found_ids)
        return jsonify({"error": f"Les utilisateurs avec les IDs suivants n'existent pas : {list(missing_ids)}"}), 404

    query = f"DELETE FROM utilisateur WHERE id IN ({format_strings})"
    try:
        cursor.execute(query, tuple(user_ids))
        connexion.commit()
    except Exception as e:
        connexion.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        connexion.close()
    
    return jsonify({"message": f"Utilisateurs supprimés avec succès : {user_ids}"}), 200

@app.route('/GetUserDetails', methods=["POST"])
def getUserDetails():
    data = request.get_json()  
    user_id = data.get("user_id")  

    if not user_id:
        return jsonify({"error": "L'ID de l'utilisateur est manquant"}), 400
    
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



@app.route('/GetClients', methods=['POST'])
def getClients():
    try:
        data = request.get_json()
        company_id = data.get('company_id')
        reference = data.get('reference')
        raison_sociale = data.get('raison_sociale')
        statut = data.get('statut')
        email = data.get('email')
        telephone = data.get('telephone')
        date_min = data.get("date_min")
        date_max = data.get('date_max')
        evaluation_min = data.get('evaluation_min')
        evaluation_max = data.get('evaluation_max')
        secteur = data.get('secteur')
        ville = data.get('ville')
        contact_nom = data.get('contact_nom')
        contact_prenom = data.get('contact_prenom')
        sort_by = data.get('sort_by')
        sort_order = data.get('sort_order', 'asc')
        page = data.get('page', 1)
        per_page = data.get('per_page', 10)
        if not company_id:
            return jsonify({"error": "company_id est obligatoire"})

        connexion = getConnexion()  
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

        if reference:
            query += " AND c.reference = %s"
            params.append(reference)
        if raison_sociale:
            query += " AND c.raison_sociale LIKE %s"
            params.append(raison_sociale + '%')
        if statut:
            query += " AND c.statut LIKE %s"
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

        query += " GROUP BY c.id"

        valid_columns = ['reference', 'raison_sociale', 'statut', 'email', 'telephone', 'date_derniere_commande', 'evaluation', 'ville']

        if sort_by and sort_by in valid_columns:
            query += " ORDER BY c." + sort_by + " " + ('DESC' if sort_order.lower() == 'desc' else 'ASC')

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
                'secteurs': row[9].split(', ') if row[9] else []  
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


@app.route('/GetClientDetails', methods=['POST'])
def getClientDetails():
    try:
        data = request.get_json()
        company_id = data.get('company_id')
        client_id = data.get('client_id')

        if not company_id or not client_id:
            return jsonify({"error": "company_id and client_id are required"}), 400
        
        connexion = getConnexion()
        cursor = connexion.cursor()
        
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

        query_secteurs = """
        SELECT s.nom
        FROM client_secteur cs
        JOIN secteur s ON cs.secteur_id = s.id
        WHERE cs.client_id = %s
        """
        cursor.execute(query_secteurs, (client_id,))
        secteurs_rows = cursor.fetchall()
        secteurs = [row[0] for row in secteurs_rows]  
        client['secteurs'] = secteurs

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

@app.route('/UpdateClient', methods=['PUT'])
def updateClient():
    try:
        data = request.get_json()
        client_id = data.get('client_id')
        if not client_id:
            return jsonify({"error": "client_id est obligatoire"})
        
        modifiable_fields = ['statut', 'evaluation', 'raison', 'info_personnelles', 'preference', 'decision']
        valid_statuses = ['risqué', 'modéré', 'fiable']
        
        for field in data.keys():
            if field not in modifiable_fields and field != "client_id":
                return jsonify({"error": f"Le champ '{field}' n'est pas modifiable."}), 400
        
        if 'statut' in data and data['statut'].lower() not in valid_statuses:
            return jsonify({"error": "Le champ 'statut' doit être l'un des suivants : 'risqué', 'modéré', 'fiable'."}), 400
        
        connexion = getConnexion()
        cursor = connexion.cursor()
        cursor.execute("SELECT COUNT(*) FROM clients WHERE id = %s", (client_id,))
        client_exists = cursor.fetchone()[0] > 0

        if not client_exists:
            return jsonify({"error": "Client not found."}), 404
        
        updates = []
        params = []

        for field in modifiable_fields:
            if field in data:
                updates.append(f"{field} = %s")
                params.append(data[field])

        if not updates:
            return jsonify({"error": "Aucun champ modifiable fourni."}), 400

        query = f"""
        UPDATE clients SET 
            {', '.join(updates)}
        WHERE id = %s
        """
        
        params.append(client_id)

        cursor.execute(query, params)
        connexion.commit()
        cursor.close()
        
        return jsonify({"message": "Client updated successfully."}), 200

    except Exception as e:
        return Response(json.dumps({'error': str(e)}), mimetype='application/json'), 500
    
###################  API pour les commandes  #####################
@app.route('/GetOrders/', methods=['POST'])
def GetOrders():
    try:
        connexion = getConnexion()
        cursor = connexion.cursor()

        data = request.get_json()

        company_id = data.get('company_id')
        client_id = data.get('client_id')
        
        numero = data.get("numero")
        date_min = data.get("date_min")
        date_max = data.get("date_max")
        montant_min = data.get("montant_min")
        montant_max = data.get("montant_max")
        date_livraison_min = data.get("date_livraison_min")
        date_livraison_max = data.get("date_livraison_max")
        etat_facture = data.get("etat_facture")
        etat_livraison = data.get("etat_livraison")
        sort_by = data.get('sort_by')
        sort_order = data.get('sort_order', 'asc')
        page = int(data.get('page', 1))
        limit = int(data.get('limit', 2))
        offset = (page - 1) * limit
        if not company_id:
            return jsonify({"error": "company_id est obligatoire"})
        if not client_id:
            return jsonify({"error": "client_id est obligatoire"})

        query = """
        SELECT c.id, c.numero, c.date_commande, c.montant, c.date_livraison, c.etat_facture, c.etat_livraison
        FROM commande c 
        JOIN clients cl ON c.ref_client = cl.id
        WHERE c.ref_client = %s and cl.company_id = %s
        """
        params = [client_id, company_id]

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
            query += " AND c.etat_facture like %s"
            params.append(etat_facture + '%')
        if etat_livraison:
            query += " AND c.etat_livraison like %s"
            params.append(etat_livraison + '%')

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


@app.route('/GetFinancialSituation', methods=["POST"])
def getFinancialSituation():
    try:
        connexion = getConnexion()
        cursor = connexion.cursor()

        # Vous pouvez récupérer des paramètres supplémentaires si nécessaire
        data = request.get_json()  # Récupération du corps de la requête si besoin
        client_id = data.get('client_id')
        if not client_id:
            return jsonify({"error": "client_id est obligatoire"})

        query = """
        SELECT c.reference, c.raison_sociale, c.statut, c.evaluation, s.ca_genere, s.montant_regle, s.encours,
        s.limite_credit, s.impaye, s.contentieux, s.provision_perte, s.preavis, s.lrs_recue
        FROM clients c
        JOIN situation_financiere s ON c.id = s.client_id
        WHERE s.client_id = %s
        """
        cursor.execute(query, (client_id,))
        result = cursor.fetchone()

        if result is None:
            return jsonify({"message": "Client not found"}), 404  # Code 404 pour "Not Found"

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

@app.route('/GetPayments', methods=["POST"])
def getPayments():
    try:
        connexion = getConnexion()
        cursor = connexion.cursor()

        # Récupération des paramètres dans le corps de la requête
        data = request.get_json()
        client_id = data.get('client_id')

        reference = data.get("reference")
        montant_min = data.get("montant_min")
        montant_max = data.get("montant_max")
        date_min = data.get("date_min")
        date_max = data.get("date_max")
        methode_paiement = data.get("methode_paiement")
        etat = data.get("etat")
        sort_by = data.get("sort_by")
        sort_order = data.get("sort_order", 'asc')
        page = int(data.get('page', 1))
        page_size = int(data.get('page_size', 2))
        offset = (page - 1) * page_size
        if not client_id:
            return jsonify({"error": "client_id est obligatoire"})

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
            query += " AND p.methode_paiement LIKE %s"
            params.append(methode_paiement + '%')
        if etat:
            query += " AND p.etat LIKE %s"
            params.append(etat + '%')

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
    finally:
        cursor.close()
        connexion.close()

@app.route('/GetSamples', methods=["POST"])
def getSamples():
    try:
        connexion = getConnexion()
        cursor = connexion.cursor()
        
        # Récupération des paramètres dans le corps de la requête
        data = request.get_json()
        client_id = data.get('client_id')
        
        sort_by = data.get('sort_by')
        sort_order = data.get('sort_order', 'asc')
        if not client_id:
            return jsonify({"error": "client_id est obligatoire"})

        query = """
        SELECT id, reference_nom, date_souhaitee, date_envoi, quantite, etat, note
        FROM echantillon
        WHERE client_id = %s
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
                'date_souhaitee': row[2].strftime('%d/%m/%Y') if row[2] else None,
                'date_envoi': row[3].strftime('%d/%m/%Y') if row[3] else None,
                'quantite': row[4],
                'etat': row[5],
                'note': row[6]
            }
            echantillons.append(produit)

        json_response = json.dumps(echantillons, ensure_ascii=False, indent=4)
        return Response(json_response, mimetype='application/json'), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500
    finally:
        cursor.close()
        connexion.close()

@app.route('/AddSample', methods=['POST'])
def addSample():
    connexion = None
    cursor = None
    try:
        data = request.get_json()
        client_id = data.get('client_id')

        reference_nom = data.get('reference_nom', '').strip() if data.get('reference_nom') else None
        date_souhaitee = data.get('date_souhaitee', '').strip() if data.get('date_souhaitee') else None
        date_envoi = data.get('date_envoi', '').strip() if data.get('date_envoi') else None
        quantite = data.get('quantite')
        etat = data.get('etat', '').strip() if data.get('etat') else None
        note = data.get('note', '').strip() if data.get('note') else None
        if not client_id:
            return jsonify({"error": "client_id est obligatoire"})
#### le nom est obligatoire (pour le moment)
        if not reference_nom:
            return jsonify({"error": "Le champ 'reference_nom' est obligatoire."}), 400
        if not etat:
            return jsonify({"error": "Le champ 'etat' est obligatoire."}), 400
        if etat:
            etat = etat.strip().lower()  
            valid_etats = ['demandé', 'envoyé', 'homologué', 'non homologué']
            if etat not in valid_etats:
                return jsonify({"error": f"L'état '{etat}' n'est pas valide. Les valeurs acceptées sont: demandé, envoyé, homologué, non homologué."}), 400
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


@app.route('/DeleteSamples', methods=['DELETE'])
def deleteSamples():
    data = request.get_json()  # Récupère les données de la requête en JSON
    sample_ids = data.get('sample_ids')  # Récupère la liste des sample_ids
    client_id = data.get('client_id')

    if not sample_ids or not isinstance(sample_ids, list):
        return jsonify({"error": "Veuillez fournir une liste valide d'IDs d'échantillons."}), 400
    if not client_id:
        return jsonify({"error": "client_id est obligatoire"})

    connexion = None
    cursor = None
    try:
        connexion = getConnexion()
        cursor = connexion.cursor()

        # Vérifie que tous les échantillons existent pour le client
        sql = "SELECT id FROM echantillon WHERE client_id = %s AND id IN (%s)" % (
            client_id, ','.join(['%s'] * len(sample_ids))
        )
        cursor.execute(sql, sample_ids)
        existing_samples = cursor.fetchall()

        existing_sample_ids = [sample[0] for sample in existing_samples]

        # Si certains échantillons ne sont pas trouvés
        if len(existing_sample_ids) != len(sample_ids):
            missing_samples = list(set(sample_ids) - set(existing_sample_ids))
            return jsonify({
                "error": "Les échantillons suivants n'existent pas pour ce client : {}".format(missing_samples)
            }), 404

        # Supprime les échantillons trouvés
        delete_sql = "DELETE FROM echantillon WHERE client_id = %s AND id IN (%s)" % (
            client_id, ','.join(['%s'] * len(sample_ids))
        )
        cursor.execute(delete_sql, sample_ids)
        connexion.commit()

        return jsonify({
            "message": "Échantillons supprimés avec succès",
            "deleted_sample_ids": existing_sample_ids,
            "client_id": client_id
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connexion:
            connexion.close()

@app.route('/UpdateSample', methods = ["PUT"])
def updateSample():
   
    data = request.json
    client_id = data.get('client_id')
    sample_id = data.get('sample_id')
    reference_nom = data.get('reference_nom', '').strip()
    date_souhaitee = data.get('date_souhaitee', '').strip()
    date_envoi = data.get('date_envoi', '').strip()
    quantite = data.get('quantite')
    etat = data.get('etat', '').strip()
    note = data.get('note', '').strip()
    if not client_id:
        return jsonify({"error": "client_id est obligatoire"})
    if not sample_id:
        return jsonify({"error": "sample_id est obligatoire"})
    
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
@app.route('/GetRecords', methods=["POST"])
def getRecords():
    try:
        # Récupération des paramètres dans le corps de la requête
        data = request.get_json()
        client_id = data.get('client_id')
        
        date_min = data.get("date_min")
        date_max = data.get("date_max")
        nom = data.get("nom")
        prenom = data.get("prenom")
        favori = data.get("favori")
        important = data.get("important")
        text = data.get('text')
        if not client_id:
            return jsonify({"error": "client_id est obligatoire"})

        connexion = getConnexion()
        cursor = connexion.cursor()

        
        query = """
        SELECT * FROM records WHERE client_id = %s
        """
        params = [client_id]

        if date_min:
            try:
                date_obj = datetime.strptime(date_min, '%d/%m/%Y %H:%M:%S').date()
                query += " AND record_date_time >= %s"
                params.append(date_obj)
            except ValueError:
                return jsonify({"error": "Invalid date format. Use dd/mm/yyyy."}), 400
        
        if date_max:
            try:
                date_obj = datetime.strptime(date_max, '%d/%m/%Y %H:%M:%S').date()
                query += " AND record_date_time <= %s"
                params.append(date_obj)
            except ValueError:
                return jsonify({"error": "Invalid date format. Use dd/mm/yyyy."}), 400
        
        if nom:
            query += " AND user_name LIKE %s"
            params.append(nom +'%')  # Utilisation de % pour faire une recherche LIKE
        if prenom:
            query += " AND prenom LIKE %s"
            params.append(prenom +'%')  # Utilisation de % pour faire une recherche LIKE
        if favori is not None:  # Vérifie si favori a été défini (peut être True ou False)
            query += " AND favori = %s"
            params.append(favori)
        if important is not None:  # Vérifie si important a été défini (peut être True ou False)
            query += " AND important = %s"
            params.append(important)
        if text:
            query += " AND record_text LIKE %s"
            params.append(f'%{text}%')  # Utilisation de % pour faire une recherche LIKE
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        records = []
        for row in rows:
            record = {
                'record_date': row[1].strftime('%d/%m/%Y %H:%M:%S') if row[1] else None,
                'record_type': row[2],
                'nom': row[3],
                'prenom': row[4],
                'record_text': row[5],
                'favori': row[6],
                'important': row[7]
            }
            records.append(record)
        
        return jsonify(records), 200
    except Exception as e:
        return jsonify({"message": str(e)}), 500
    finally:
        cursor.close()
        connexion.close()



@app.route('/AddRecord', methods = ["POST"])
def addRecord():
    connexion = getConnexion()
    cursor = connexion.cursor()
    try:
        data = request.get_json()
        client_id = data.get('client_id')
        record_time = data.get('record_time', '').strip() if data.get('record_time') else None
        record_type = data.get('record_type', '').strip().lower() 
        nom = data.get('nom', '')
        prenom = data.get('prenom', '')
        record_text = data.get('record_text', '')
        favori = data.get('favori')
        important = data.get('important')
        if not client_id:
            return jsonify({"error": "client_id est obligatoire"})

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
@app.route('/GetProductsList', methods=['POST'])
def getProductsList():
    try:
        # Récupération des paramètres dans le corps de la requête
        data = request.get_json()
        company_id = data.get('company_id')

        # Paramètres de recherche
        reference = data.get('reference')
        nom = data.get('nom')
        date_min = data.get('date_min') 
        date_max = data.get('date_max')
        quantite_min = data.get('quantite_min')
        quantite_max = data.get('quantite_max')
        secteur = data.get('secteur')
        sort_by = data.get('sort_by')
        sort_order = data.get('sort_order', 'asc')

        # Pagination
        page = int(data.get('page', 1))
        limit = int(data.get('limit', 3))
        offset = (page - 1) * limit

        # Vérification de la présence de company_id
        if not company_id:
            return jsonify({"error": "company_id est obligatoire"}), 400

        # Connexion à la base de données
        connexion = getConnexion()
        cursor = connexion.cursor()

        # Début de la requête SQL
        query = """
            SELECT p.id, p.reference, p.nom, p.date_derniere_commande, p.quantite_stock, GROUP_CONCAT(s.nom SEPARATOR ', ') as secteurs
            FROM produit p 
            LEFT JOIN produit_secteur ps ON p.id = ps.produit_id
            LEFT JOIN secteur s ON ps.secteur_id = s.id
            WHERE p.company_id = %s
        """
        params = [company_id]
        conditions = []

        # Ajout des filtres dynamiques
        if reference:
            conditions.append("p.reference = %s")
            params.append(reference)
        if nom:
            conditions.append("p.nom LIKE %s")
            params.append(nom + '%')
        if date_min:
            try:
                date_obj = datetime.strptime(date_min, '%d/%m/%Y').date()
                conditions.append("p.date_derniere_commande >= %s")
                params.append(date_obj)
            except ValueError:
                return jsonify({"error": "Format de date incorrect. Utilisez jj/mm/aaaa."}), 400
        if date_max:
            try:
                date_obj = datetime.strptime(date_max, '%d/%m/%Y').date()
                conditions.append("p.date_derniere_commande <= %s")
                params.append(date_obj)
            except ValueError:
                return jsonify({"error": "Format de date incorrect. Utilisez jj/mm/aaaa."}), 400
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

        # Ajout des conditions à la requête SQL
        if conditions:
            query += " AND " + " AND ".join(conditions)

        # Ajout de GROUP BY et ORDER BY
        query += """
            GROUP BY p.id, p.reference, p.nom, p.date_derniere_commande, p.quantite_stock
        """

        if sort_by:
            order = "DESC" if sort_order.lower() == 'desc' else "ASC"
            query += f" ORDER BY p.{sort_by} {order}"

        # Ajout de LIMIT et OFFSET pour la pagination
        query += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        # Exécution de la requête
        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Traitement des résultats
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

        # Conversion en JSON et réponse
        json_response = json.dumps(produits, ensure_ascii=False, indent=4)
        return Response(json_response, mimetype='application/json'), 200

    except Exception as e:
        # Gestion des erreurs
        return Response(json.dumps({'error': str(e)}), mimetype='application/json'), 500

@app.route('/GetProductDetails', methods=["POST"])
def getProductDetails():
    try:
        # Récupération des données dans le corps de la requête
        data = request.get_json()
        product_id = data.get('product_id')
        connexion = getConnexion()
        cursor = connexion.cursor()
        if not product_id:
            return jsonify({"error": "product_id est obligatoire"})

        query = """
        SELECT p.reference, p.nom, p.quantite_stock, p.prix_vente, p.note_commentaire
        FROM produit p
        WHERE p.id = %s
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
        SELECT s.nom FROM produit_secteur ps
        JOIN secteur s ON ps.secteur_id = s.id
        WHERE ps.produit_id = %s
        """
        cursor.execute(query_secteurs, (product_id,))
        secteurs_rows = cursor.fetchall()
        secteurs = [row[0] for row in secteurs_rows]
        product['secteurs'] = secteurs

        query_variante = f"""
        SELECT vp.id, v.valeur, vp.quantite_en_stock, vp.seuil, vp.prix_vente_objectif, vp.prix_vente_min,
        vp.date_derniere_commande, vp.date_expiration 
        FROM variantes v
        JOIN variante_produit vp 
        ON v.id = vp.variante_id
        WHERE produit_id = %s
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

        json_response = json.dumps(product, ensure_ascii=False, indent=4)
        return Response(json_response, mimetype='application/json'), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 500

    finally:
        cursor.close()
        connexion.close()


@app.route('/UpdateProduct', methods=['PUT'])
def updateProduct():
    connexion = None
    cursor = None
    try:
        data = request.get_json()
        product_id = data.get('product_id')

        if not product_id:
            return jsonify({"error": "product_id est obligatoire"}), 400

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
        if cursor:
            cursor.close()
        if connexion:
            connexion.close()


@app.route('/GetProducts', methods=['POST'])
def getProducts():
    try:
        # Obtenir le terme de recherche à partir du corps de la requête JSON
        data = request.get_json()
        search_term = data.get('search_term', '')

        connexion = getConnexion()
        cursor = connexion.cursor()

        query = """
        SELECT id, ref_article, nom
        FROM article
        WHERE ref_article LIKE %s OR nom LIKE %s
        ORDER BY nom ASC
        """
        
        search_term_like = f'{search_term}%'

        cursor.execute(query, (search_term_like, search_term_like))
        rows = cursor.fetchall()

        if not rows:
            return jsonify({"error": "No products found"}), 404
        
        products = []
        for row in rows:
            product = {
                "id": row[0],
                "ref_article": row[1],
                "nom": row[2]
            }
            products.append(product)

        return jsonify(products), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        connexion.close()

@app.route('/GetProductPurchase/<int:product_id>', methods=["POST"]) ### to V1
def getProductPurchase(product_id):
    try:
        data = request.get_json()

        numero = data.get('numero')
        reference = data.get('reference')
        fournisseur = data.get('fournisseur')
        etat_paiement = data.get('etat_paiement')
        date_min = data.get('date_min')
        date_max = data.get('date_max')
        montant_min = data.get('montant_min')
        montant_max = data.get('montant_max')
        sort_by = data.get('sort_by')
        sort_order = data.get('sort_order', 'asc')
        page = int(data.get('page', 1)) 
        per_page = int(data.get('per_page', 1))

        connexion = getConnexion()
        cursor = connexion.cursor()

        query = """
        SELECT a.id, a.numero_facture, f.reference, f.nom_fournisseur, a.date_facturation, a.montant, a.etat_paiement
        FROM achat_produit a
        JOIN fournisseur f ON f.id = a.fournisseur_id
        WHERE a.produit_id = %s
        """
        
        params = [product_id]
        
        if numero:
            query += " AND a.numero_facture = %s"
            params.append(numero)
        if reference:
            query += " AND f.reference = %s"
            params.append(reference)
        if fournisseur:
            query += " AND f.nom_fournisseur LIKE %s"
            params.append(fournisseur + '%')
        if etat_paiement:
            query += " AND a.etat_paiement LIKE %s"
            params.append(etat_paiement + '%')
        if date_min:
            try:
                date_obj = datetime.strptime(date_min, '%d/%m/%Y').date()
                query += " AND a.date_facturation >= %s"
                params.append(date_obj)
            except ValueError:
                return jsonify({"error": "Invalid date format. Use dd/mm/yyyy."}), 400
        if date_max:
            try:
                date_obj = datetime.strptime(date_max, '%d/%m/%Y').date()
                query += " AND a.date_facturation <= %s"
                params.append(date_obj)
            except ValueError:
                return jsonify({"error": "Invalid date format. Use dd/mm/yyyy."}), 400
        if montant_min:
            query += " AND a.montant >= %s"
            params.append(montant_min)
        if montant_max:
            query += " AND a.montant <= %s"
            params.append(montant_max)

        if sort_by in ['numero_facture', 'reference', 'nom_fournisseur', 'date_facturation', 'montant', 'etat_paiement']:
            query += f" ORDER BY {sort_by} {sort_order}"

        offset = (page - 1) * per_page
        query += " LIMIT %s OFFSET %s"
        params.extend([per_page, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()

        produits = []
        for row in rows:
            produit = {
                'id': row[0],
                'numero_facture': row[1],
                'reference': row[2],
                'nom_fournisseur': row[3],
                'date_facturation': row[4].strftime('%d/%m/%Y') if row[4] else None,
                'montant': row[5],
                'etat_paiement': row[6]
            }
            produits.append(produit)

        json_response = json.dumps(produits, ensure_ascii=False, indent=4)
        return Response(json_response, mimetype='application/json'), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        connexion.close()


@app.route('/GetProductSales', methods=["POST"])
def getProductSales():
    try:
        # Retrieve parameters from JSON body
        data = request.json
        product_id = data.get('product_id')
        numero_facture = data.get('numero_facture')
        reference_client = data.get('reference_client')
        raison_sociale = data.get('raison_sociale')
        date_facturation_min = data.get('date_facturation_min')
        date_facturation_max = data.get('date_facturation_max')
        date_echeance_min = data.get('date_echeance_min')
        date_echeance_max = data.get('date_echeance_max')
        montant_min = data.get('montant_min')
        montant_max = data.get('montant_max')
        etat_paiement = data.get('etat_paiement')
        sort_by = data.get('sort_by')
        sort_order = data.get('sort_order', 'asc')
        page = int(data.get('page', 1))
        per_page = int(data.get('per_page', 2))
        if not product_id:
            return jsonify({"error": "product_id est obligatoire"})

        connexion = getConnexion()
        cursor = connexion.cursor()

        query = """
        SELECT v.id, v.numero_facture, c.reference, c.raison_sociale, v.date_facturation, v.date_echeance,
        v.montant, v.etat_paiement FROM vente_produit v
        JOIN clients c ON v.client_id = c.id
        WHERE v.produit_id = %s
        """
        params = [product_id]

        if numero_facture:
            query += " AND v.numero_facture = %s"
            params.append(numero_facture)
        if reference_client:
            query += " AND c.reference = %s"
            params.append(reference_client)
        if raison_sociale:
            query += " AND c.raison_sociale LIKE %s"
            params.append(raison_sociale + '%')
        if date_facturation_min:
            try:
                date_obj = datetime.strptime(date_facturation_min, '%d/%m/%Y').date()
                query += " AND v.date_facturation >= %s"
                params.append(date_obj)
            except ValueError:
                return jsonify({"error": "Invalid date format. Use dd/mm/yyyy."}), 400
        if date_facturation_max:
            try:
                date_obj = datetime.strptime(date_facturation_max, '%d/%m/%Y').date()
                query += " AND v.date_facturation <= %s"
                params.append(date_obj)
            except ValueError:
                return jsonify({"error": "Invalid date format. Use dd/mm/yyyy."}), 400
        if date_echeance_min:
            try:
                date_obj = datetime.strptime(date_echeance_min, '%d/%m/%Y').date()
                query += " AND v.date_echeance >= %s"
                params.append(date_obj)
            except ValueError:
                return jsonify({"error": "Invalid date format. Use dd/mm/yyyy."}), 400
        if date_echeance_max:
            try:
                date_obj = datetime.strptime(date_echeance_max, '%d/%m/%Y').date()
                query += " AND v.date_echeance <= %s"
                params.append(date_obj)
            except ValueError:
                return jsonify({"error": "Invalid date format. Use dd/mm/yyyy."}), 400
        if montant_min:
            query += " AND v.montant >= %s"
            params.append(montant_min)
        if montant_max:
            query += " AND v.montant <= %s"
            params.append(montant_max)
        if etat_paiement:
            query += " AND v.etat_paiement LIKE %s"
            params.append(etat_paiement + '%')
        if sort_by in ["numero_facture", "reference", "raison_sociale", "date_facturation", "date_echeance", "montant", "etat_paiement"]:
            query += f" ORDER BY {sort_by} {sort_order}"

        offset = (page - 1) * per_page
        query += " LIMIT %s OFFSET %s"
        params.extend([per_page, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()
        sales = []
        for row in rows:
            sale = {
                'id': row[0],
                'numero_facture': row[1],
                'reference': row[2],
                'raison_sociale': row[3],
                'date_facturation': row[4].strftime('%d/%m/%Y') if row[4] else None,
                'date_echeance': row[5].strftime('%d/%m/%Y') if row[5] else None,
                'montant': row[6],
                'etat_paiement': row[7]
            }
            sales.append(sale)

        json_response = json.dumps(sales, ensure_ascii=False, indent=4)
        return Response(json_response, mimetype='application/json'), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        connexion.close()

@app.route('/GetSamplesOfProduct', methods=["POST"])
def getSamplesOfProduct():
    try:
        # Retrieve parameters from JSON body
        data = request.json
        product_id = data.get('product_id')
        reference_client = data.get('reference_client')
        raison_sociale = data.get('raison_sociale')
        date_souhaitee_min = data.get('date_souhaitee_min')
        date_souhaitee_max = data.get('date_souhaitee_max')
        date_envoi_min = data.get('date_envoi_min')
        date_envoi_max = data.get('date_envoi_max')
        quantite_min = data.get('quantite_min')
        quantite_max = data.get('quantite_max')
        etat = data.get('etat')
        note = data.get('note')
        sort_by = data.get('sort_by')
        sort_order = data.get('sort_order', 'asc')
        page = int(data.get('page', 1))
        per_page = int(data.get('per_page', 2))

        if not product_id:
            return jsonify({"error": "product_id est obligatoire"})

        connexion = getConnexion()
        cursor = connexion.cursor()

        query = """
        SELECT e.id,
               CASE 
                   WHEN c.raison_sociale IS NOT NULL THEN c.reference 
                   ELSE NULL 
               END AS reference,
               CASE 
                   WHEN c.raison_sociale IS NOT NULL THEN c.raison_sociale 
                   ELSE e.raison_sociale 
               END AS raison_sociale,
               e.date_souhaitee, 
               e.date_envoi, 
               e.quantite, 
               e.etat, 
               e.note
        FROM echantillon e
        LEFT JOIN clients c ON c.raison_sociale = e.raison_sociale
        WHERE e.produit_id = %s
        """
        params = [product_id]

        if reference_client:
            query += " AND c.reference = %s"
            params.append(reference_client)
        if raison_sociale:
            query += " AND (c.raison_sociale like %s OR e.raison_sociale like %s)"
            params.append(raison_sociale +'%')
            params.append(raison_sociale +'%')
        if date_souhaitee_min:
            try:
                date_obj = datetime.strptime(date_souhaitee_min, '%d/%m/%Y').date()
                query += " AND e.date_souhaitee >= %s"
                params.append(date_obj)
            except ValueError:
                return jsonify({"error": "Invalid date format. Use dd/mm/yyyy."}), 400 
        if date_souhaitee_max:
            try:
                date_obj = datetime.strptime(date_souhaitee_max, '%d/%m/%Y').date()
                query += " AND e.date_souhaitee <= %s"
                params.append(date_obj)
            except ValueError:
                return jsonify({"error": "Invalid date format. Use dd/mm/yyyy."}), 400 
        if date_envoi_min:
            try:
                date_obj = datetime.strptime(date_envoi_min, '%d/%m/%Y').date()
                query += " AND e.date_envoi >= %s"
                params.append(date_obj)
            except ValueError:
                return jsonify({"error": "Invalid date format. Use dd/mm/yyyy."}), 400 
        if date_envoi_max:
            try:
                date_obj = datetime.strptime(date_envoi_max, '%d/%m/%Y').date()
                query += " AND e.date_envoi <= %s"
                params.append(date_obj)
            except ValueError:
                return jsonify({"error": "Invalid date format. Use dd/mm/yyyy."}), 400 
        if quantite_min:
            query += " AND e.quantite >= %s"
            params.append(quantite_min)
        if quantite_max:
            query += " AND e.quantite <= %s"
            params.append(quantite_max)
        if etat:
            query += " AND e.etat like %s"
            params.append(etat +'%')
        if note:
            query += " AND e.note LIKE %s"
            params.append('%' + note + '%')

        if sort_by in ["reference", "raison_sociale", "date_souhaitee", "date_envoi", "quantite", "etat", "note"]:
            query += f" ORDER BY {sort_by} {sort_order}"

        offset = (page - 1) * per_page
        query += " LIMIT %s OFFSET %s"
        params.extend([per_page, offset])

        cursor.execute(query, params)
        rows = cursor.fetchall()
        samples = []

        for row in rows:
            sample = {
                'id': row[0],
                'reference': row[1],
                'raison_sociale': row[2],
                'date_souhaitee': row[3].strftime('%d/%m/%Y') if row[3] else None,
                'date_envoi': row[4].strftime('%d/%m/%Y') if row[4] else None,
                'quantite': row[5],
                'etat': row[6],
                'note': row[7]
            }
            samples.append(sample)

        json_response = json.dumps(samples, ensure_ascii=False, indent=4)
        return Response(json_response, mimetype='application/json'), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        connexion.close()

@app.route('/GetProductSampleDetails', methods=["POST"])
def getProductSampleDetails():
    cursor = None
    connexion = None
    try:
        data = request.get_json()
        product_id = data.get('product_id')
        sample_id = data.get('sample_id')
        if not product_id:
            return jsonify({"error": "product_id est obligatoire"}), 400
        if not sample_id:
            return jsonify({"error": "sample_id est obligatoire"}), 400
        
        connexion = getConnexion()
        cursor = connexion.cursor()

        query = """
        SELECT e.raison_sociale, e.date_souhaitee, e.date_envoi, e.quantite, e.etat, e.note
        FROM echantillon e
        WHERE e.produit_id = %s AND e.id = %s
        """
        params = [product_id, sample_id]
        cursor.execute(query, params)
        row = cursor.fetchone()

        if row:
            detail = {
                'raison_sociale': row[0],
                'date_souhaitee': row[1].strftime('%d/%m/%Y') if row[1] else None,
                'date_envoi': row[2].strftime('%d/%m/%Y') if row[2] else None,
                'quantite': row[3],
                'etat': row[4],
                'note': row[5]
            }
            json_response = json.dumps(detail, ensure_ascii=False, indent=4)
            return Response(json_response, mimetype='application/json'), 200
        else:
            return jsonify({"error": "Sample not found"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connexion:
            connexion.close()

@app.route('/AddSampleOfProduct', methods=["POST"])
def addSampleOfProduct():
    try:
        connexion = getConnexion()
        cursor = connexion.cursor()
        data = request.get_json()
        product_id = data.get('product_id')
        raison_sociale = data.get('raison_sociale', '').strip() if data.get('raison_sociale') else None
        date_souhaitee = data.get('date_souhaitee', '').strip() if data.get('date_souhaitee') else None
        date_envoi = data.get('date_envoi', '').strip() if data.get('date_envoi') else None
        quantite = data.get('quantite')
        etat = data.get('etat', '').strip() if data.get('etat') else None
        note = data.get('note', '').strip() if data.get('note') else None

        if not product_id:
            return jsonify({"error": "product_id est obligatoire"})

        if not raison_sociale:
            return jsonify({"error": "Le champ raison sociale est obligatoire"}), 400
        if not etat:
            return jsonify({"error": "Le champ etat est obligatoire"}), 400
        
        etat = etat.strip().lower()
        valid_etat = ["demandé", "envoyé", "homologué", "non homologué"]
        if etat not in valid_etat:
            return jsonify({"error": "L'état n'est pas valide"}), 400
        
        date_souhaitee_obj = None
        date_envoi_obj = None
        try:
            if date_souhaitee:
                date_souhaitee_obj = datetime.strptime(date_souhaitee, '%d/%m/%Y').date()
            if date_envoi:
                date_envoi_obj = datetime.strptime(date_envoi, '%d/%m/%Y').date()
        except ValueError:
            return jsonify({"error": "Date invalide, veuillez utiliser le format dd/mm/yyyy"}), 400

        query = """
        INSERT INTO echantillon (date_souhaitee, date_envoi, quantite, etat, note, produit_id, raison_sociale)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        params = (date_souhaitee_obj, date_envoi_obj, quantite, etat, note, product_id, raison_sociale)
        try:
            cursor.execute(query, params)
            connexion.commit()
            new_sample_id = cursor.lastrowid
        except Exception as e:
            connexion.rollback()
            return jsonify({"error": str(e)}), 500


        return jsonify({"message": "Échantillon ajouté avec succès", "sample_id": new_sample_id}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        cursor.close()
        connexion.close()

@app.route('/GetCompanyName', methods=["POST"])
def getCompanyName():
    try:
        connexion = getConnexion()
        cursor = connexion.cursor()

        # Obtenir le terme de recherche à partir du corps de la requête
        data = request.get_json()
        search_term = data.get('search_term', '')

        query = """
        SELECT id, raison_sociale FROM clients
        WHERE raison_sociale LIKE %s
        ORDER BY raison_sociale ASC
        """
        search_term_like = f'{search_term}%'
        cursor.execute(query, (search_term_like,))
        rows = cursor.fetchall()

        if not rows:
            return jsonify({"error": "no company name found"}), 404  # Retourne 404 si aucune entreprise n'est trouvée

        companyNames = []
        for row in rows:
            company = {
                'id': row[0],
                'raison_sociale': row[1]
            }
            companyNames.append(company)

        return jsonify(companyNames), 200  # Retourne la liste des entreprises au format JSON
    except Exception as e:
        return jsonify({"error": str(e)}), 500  # Retourne une erreur interne du serveur
    finally:
        if cursor:
            cursor.close()
        if connexion:
            connexion.close()


@app.route('/UpdateSampleOfProduct', methods=["PUT"])
def updateSampleOfProduct():
    connexion = getConnexion()
    cursor = connexion.cursor()

    data = request.get_json()
    product_id = data.get('product_id')
    sample_id = data.get('sample_id')
    raison_sociale = data.get('raison_sociale', '').strip()
    date_souhaitee = data.get('date_souhaitee', '').strip() if data.get('date_souhaitee') else None
    date_envoi = data.get('date_envoi', '').strip() if data.get('date_envoi') else None
    quantite = data.get('quantite')
    etat = data.get('etat', '').strip()
    note = data.get('note', '').strip()
    
    if not product_id:
        return jsonify({"error": "product_id est obligatoire"})
    if not sample_id:
        return jsonify({"error": "sample_id est obligatoire"})

    # Vérification de l'état
    valid_etat = ["demandé", "envoyé", "homologué", "non homologué"]
    if etat and etat.lower() not in valid_etat:
        return jsonify({"error": "L'état doit être l'un des suivants : 'demandé', 'envoyé', 'homologué', 'non homologué'"}), 400

    def convert_to_date(date_str):
        if date_str:
            try:
                return datetime.strptime(date_str, '%d/%m/%Y').strftime('%Y-%m-%d')
            except ValueError:
                return None
        return None

    date_souhaitee_db = convert_to_date(date_souhaitee)
    date_envoi_db = convert_to_date(date_envoi)

    if (date_souhaitee and not date_souhaitee_db) or (date_envoi and not date_envoi_db):
        return jsonify({"error": "Format de date invalide, veuillez utiliser dd/mm/yyyy"}), 400

    cursor.execute("SELECT * FROM echantillon WHERE id = %s AND produit_id = %s", (sample_id, product_id))
    echantillon = cursor.fetchone()
    if not echantillon:
        return jsonify({"error": "Echantillon non trouvé"})

    update_fields = []
    params = []
    if raison_sociale:
        update_fields.append("raison_sociale = %s")
        params.append(raison_sociale)
    if date_souhaitee_db:
        update_fields.append("date_souhaitee = %s")
        params.append(date_souhaitee_db)
    if date_envoi_db:
        update_fields.append("date_envoi = %s")
        params.append(date_envoi_db)
    if quantite:
        update_fields.append("quantite = %s")
        params.append(quantite)
    if etat:
        update_fields.append("etat = %s")
        params.append(etat)
    if note:
        update_fields.append("note = %s")
        params.append(note)

    if not update_fields:
        return jsonify({"error": "Aucune donnée à mettre à jour"})

    query = "UPDATE echantillon SET " + ", ".join(update_fields) + " WHERE id = %s AND produit_id = %s"
    params.extend([sample_id, product_id])

    try:
        cursor.execute(query, params)
        connexion.commit()
    except Exception as e:
        connexion.rollback()
        return jsonify({"error": str(e)})
    finally:
        cursor.close()
        connexion.close()

    return jsonify({"message": "Echantillon mis à jour avec succès"})

@app.route('/DeleteSamplesOfProduct', methods=["DELETE"])
def deleteSamplesOfProduct():
    connexion = None
    cursor = None
    try:
        connexion = getConnexion()
        cursor = connexion.cursor()

        request_data = request.get_json()
        product_id = request_data.get('product_id')
        sample_ids = request_data.get('sample_ids')

        if not product_id:
            return jsonify({"error": "product_id est obligatoire"})

        if not sample_ids or not isinstance(sample_ids, list):
            return jsonify({"error": "Veuillez fournir une liste valide d'IDs d'échantillons."}), 400

        placeholders = ', '.join(['%s'] * len(sample_ids))  
        cursor.execute(f"SELECT * FROM echantillon WHERE id IN ({placeholders}) AND produit_id = %s", (*sample_ids, product_id))
        existing_samples = cursor.fetchall()

        if not existing_samples:
            return jsonify({"error": "Aucun échantillon trouvé pour ce produit."}), 404

        query = f"DELETE FROM echantillon WHERE id IN ({placeholders}) AND produit_id = %s"
        cursor.execute(query, (*sample_ids, product_id))
        connexion.commit()

        return jsonify({
            "message": "Échantillons supprimés avec succès",
            "deleted_sample_ids": sample_ids,
            "product_id": product_id
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if cursor:
            cursor.close()
        if connexion:
            connexion.close()

if __name__ == "__main__":
    app.run(debug=True)
