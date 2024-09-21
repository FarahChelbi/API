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
    
    base_query = "SELECT * FROM companies"
    params = []
    if sort_order:
        if sort_order.lower() == 'desc':
            base_query += " ORDER BY nom DESC"
        elif sort_order.lower() == 'asc':
            base_query += " ORDER BY nom ASC"
    
    cursor.execute(base_query, tuple(params))
    
    rows = cursor.fetchall()
    companies = [{'id': row[0], 'nom': row[1]} for row in rows]
    
    cursor.close()
    connexion.close()
    return jsonify(companies)

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
        sort_by = request.args.get('sort_by')
        sort_order = request.args.get('sort_order','asc')
        connexion = getConnexion()
        cursor = connexion.cursor()

        query = """
        SELECT c.id, c.reference, c.raison_sociale, c.statut, c.email, c.telephone, 
               c.date_derniere_commande, c.evaluation, c.ville, s.nom as secteur
        FROM clients c
        JOIN secteur s ON c.secteur_id = s.id
        JOIN companies comp ON c.company_id = comp.id
        LEFT JOIN contacts ct ON ct.client_id = c.id
        WHERE comp.id = %s
        """
        
        params = [company_id]

        if reference:
            query += " and c.reference = %s"
            params.append(reference)
        if raison_sociale:
            query += " and c.raison_sociale like %s"
            params.append(raison_sociale+'%')
        if statut:
            query += " and c.statut = %s"
            params.append(statut)
        if email:
            query += " and c.email = %s"
            params.append(email)
        if telephone:
            query += " and (c.telephone = %s or c.mobile = %s or ct.telephone = %s or ct.mobile = %s)"
            params.extend([telephone, telephone, telephone, telephone])
        if date_min:
            try:
                date_obj = datetime.strptime(date_min, '%d/%m/%Y').date()
                query += " AND c.date_derniere_commande >= %s"
                params.append(date_obj)
            except ValueError as e:
                return jsonify({"error": "Invalid date format. Use dd/mm/yyyy."}), 400
        if date_max:
            try:
                date_obj = datetime.strptime(date_max, '%d/%m/%Y').date()
                query += " AND c.date_derniere_commande <= %s"
                params.append(date_obj)
            except ValueError as e:
                return jsonify({"error": "Invalid date format. Use dd/mm/yyyy."}), 400
        if evaluation_min:
            query += " and c.evaluation >= %s"
            params.append(evaluation_min)
        if evaluation_max:
            query += " and c.evaluation <= %s"
            params.append(evaluation_max)
        if ville:
            query += " and c.ville like %s"
            params.append(ville+'%')
        if secteur:
            query += " and s.nom = %s"
            params.append(secteur)
        if contact_nom:
            query += " and ct.nom like %s"  
            params.append(contact_nom+'%')
        if sort_by:
            if sort_order.lower() == 'desc':
                query += " ORDER BY c.{} DESC".format(sort_by)
            else:
                query += " ORDER BY c.{} ASC".format(sort_by)
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
                'date_derniere_commande':row[6].strftime('%d/%m/%Y') if row[6] else None,
                'evaluation': row[7],
                'ville': row[8],
                'secteur': row[9]
            }
            clients.append(client)

        cursor.close()

        return jsonify(clients)

    except Exception as e:
        # Gestion des erreurs
        return Response(json.dumps({'error': str(e)}), mimetype='application/json'), 500


app.route('/GetClientDetails/<int:client_id>', methods=['GET'])
def getClientDetails(client_id):
    try:
        connexion = getConnexion()
        cursor = connexion.cursor()

        
    except Exception as e:
        return jsonify({"message": str(e)}), 500
    finally:
        cursor.close()
        connexion.close()  
if __name__ == "__main__":
    app.run(debug=True)
