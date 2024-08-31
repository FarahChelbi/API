from flask import Flask , jsonify, request, Response
import mysql.connector
from mysql.connector import errorcode, Error
import requests
from datetime import datetime
from collections import OrderedDict
import json


"""
si on veut une table avec une seule colonne "nom" sans les id, on change sur l'indice du row 
"""

app = Flask(__name__)

def createDataBase(host, user, password, database_name):
    try:
        connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password
        )
        cursor = connection.cursor()
        query = "create database if not exists {}".format(database_name)
        cursor.execute(query)
        print("done")

    except mysql.connector.Error as e:
        if e.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("probleme avec le username ou password")
        else:
            print(e)
    else:
        cursor.close()
        connection.close()

def getConnection(): # à changer apres 
    return mysql.connector.connect(
        host = "127.0.0.1",
        user = "root",
        password = "root",
        database = "khouldoun"
    )

def test_connection():
    connection  = getConnection()
    if connection.is_connected():
        print("Connected to MySQL database")
    return connection

# done : tri et recherche par nom
@app.route('/GetCompanies', methods=['GET'])  
def getCompanies():
    sort_order = request.args.get('sort_order')
    connection = test_connection()
    cursor = connection.cursor()
    
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
    connection.close()
    
    return jsonify(companies)


# done

@app.route('/GetClients', methods=['GET'])
def getClients():
    # ce champ est oblig 
    nom_entreprise = request.args.get('nom_entreprise')
    # les filtres à utiliser 
    reference = request.args.get('reference')
    nom = request.args.get("nom")
    status = request.args.get("status")
    email = request.args.get("email")
    telephone = request.args.get("telephone")
    date_debut = request.args.get("date_debut")
    date_fin = request.args.get("date_fin")

    evaluation_min = request.args.get("evaluation_min")
    evaluation_max = request.args.get("evaluation_max")
    secteur = request.args.get("secteur")
    ville = request.args.get("ville")

    sort_by = request.args.get('sort_by')
    sort_order = request.args.get('sort_order','asc') 
    
    if not nom_entreprise:
        return jsonify({"error": "nom_entreprise parameter is required"}), 400
    
    connection = getConnection()
    cursor = connection.cursor()
    
    
    base_query = """
        SELECT c.id, c.reference, c.nom, c.status, c.email, c.telephone, c.date_derniere_commande,
               c.evaluation, c.secteur, c.ville
        FROM clients c
        JOIN companies comp ON c.company_id = comp.id
        WHERE comp.nom = %s
    """
    params = [nom_entreprise]
    
    if reference:
        base_query += " AND c.reference = %s"
        params.append(reference)
    
    if nom:
        base_query += "AND c.nom LIKE %s"
        params.append(nom +'%')
    if status:
        base_query += "AND c.status = %s"
        params.append(status)
    if email:
        base_query += "AND c.email = %s"
        params.append(email)
    if telephone:
        base_query += "AND c.telephone like %s"
        params.append(telephone +'%')
    if date_debut:
        try:
            date_obj = datetime.strptime(date_debut, '%Y-%m-%d').date()
            base_query += " AND c.date_derniere_commande >= %s"
            params.append(date_obj)
        except ValueError as e:
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400
    
    if date_fin:
        try:
            date_obj = datetime.strptime(date_fin, '%Y-%m-%d').date()
            base_query += " AND c.date_derniere_commande <= %s"
            params.append(date_obj)
        except ValueError as e:
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400
    if evaluation_min:
        base_query += "AND c.evaluation >= %s"
        params.append(evaluation_min)
    if evaluation_max:
        base_query += "AND c.evaluation <= %s"
        params.append(evaluation_max)
    if secteur:
        base_query += "AND c.secteur like %s"
        params.append(secteur +'%')
    if ville:
        base_query += "AND c.ville like %s"
        params.append(ville +'%')

    if sort_by:
        if sort_order.lower() == 'desc':
            base_query += " ORDER BY c.{} DESC".format(sort_by)
        else:
            base_query += " ORDER BY c.{} ASC".format(sort_by)
    
    cursor.execute(base_query, tuple(params))
    rows = cursor.fetchall()
    
    clients = []
    
    for row in rows:
        client = {
            'id' : row[0],
            'reference': row[1],
            'nom': row[2],
            'status': row[3],
            'email': row[4],
            'telephone': row[5],
            'date_derniere_commande': row[6].isoformat() if row[6] else None,
            'evaluation': row[7],
            'secteur': row[8],
            'ville': row[9]
        }
        clients.append(client)
        
    
    cursor.close()
    connection.close()
    json_response = json.dumps(clients, ensure_ascii=False, indent=4)
    return Response(json_response, mimetype='application/json'), 200
    #return jsonify(clients)


# done
@app.route('/GetClientDetails/<reference>', methods=['GET'])
def getClientDetail(reference):
    try:
        
        connection = getConnection()
        cursor = connection.cursor()

        columns = ["c.nom", "c.status", "c.email", "c.telephone", "c.tel2", "c.tel3", "c.fax", "c.site_web", "c.date_derniere_commande", "c.secteur", "c.adr_ligne1", "c.adr_ligne2", "c.code_postal", "c.ville", "c.pays", "c.info_personnelles", "c.preference", "c.decision", "c.visite", "comp.nom AS nom_entreprise"]
        query = f"""
        SELECT {', '.join(columns)}
        FROM clients c
        JOIN companies comp ON c.company_id = comp.id
        WHERE c.id = %s
        """
        cursor.execute(query, (reference,))
        client = cursor.fetchone()

        if client:
            client_columns = [col.split(' AS ')[-1] if ' AS ' in col else col.split('.')[-1] for col in columns]
            client_details = OrderedDict(zip(client_columns, client))

            
            if client_details["date_derniere_commande"]:
                client_details["date_derniere_commande"] = client_details["date_derniere_commande"].isoformat()

            

            query_contacts = """
            SELECT c.id, c.nom, c.prenom, c.fonction, c.tel1, c.tel2, c.tel3, c.fax, c.email, c.adr_ligne1, c.adr_ligne2, c.code_postal, c.ville, c.pays
            FROM contact c
            JOIN clients cl ON c.ref_client = cl.id
            WHERE cl.id = %s
            """
            params = [reference]

            cursor.execute(query_contacts, tuple(params))
            contacts = cursor.fetchall()
            contacts_list = [OrderedDict(zip(["id","nom", "prenom", "fonction", "tel1", "tel2", "tel3", "fax", "email", "adr_ligne1", "adr_ligne2", "code_postal", "ville", "pays"], contact)) for contact in contacts]

            
            response_data = {
                "client_details": client_details,
                "contacts": contacts_list
            }

            json_response = json.dumps(response_data, ensure_ascii=False, indent=4)
            return Response(json_response, mimetype='application/json'), 200
        else:
            return jsonify({"message": "Client non trouvé"}), 404
    except Exception as e:
        return jsonify({"message": str(e)}), 500
    finally:
        cursor.close()
        connection.close()

#done
@app.route('/GetOrders/<reference>', methods=['GET'])
def GetOrders(reference):
    try:
        connection = getConnection()
        cursor = connection.cursor()

        status = request.args.get("status")
        date_debut = request.args.get("date_debut")
        date_fin = request.args.get("date_fin")
        montant_min = request.args.get("montant_min")
        montant_max = request.args.get("montant_max")
        ref_commande = request.args.get("ref_commande")
        nom_article = request.args.get("nom_article")
        sort_by = request.args.get('sort_by')
        sort_order = request.args.get('sort_order','asc')

        query = """
        SELECT c.id, c.ref_commande, c.date_commande, 
       c.montant, c.status
            FROM commande c
            JOIN commande_article ca ON c.id = ca.id_commande
            JOIN article a ON ca.id_article = a.id
            join clients cl on c.ref_client = cl.id
            WHERE cl.id = %s
        """
        params = [reference]

        if status:
            query += " AND c.status = %s"
            params.append(status)
        
        if date_debut:
            try:
                date_obj = datetime.strptime(date_debut, '%Y-%m-%d').date()
                query += " AND c.date_commande >= %s"
                params.append(date_obj)
            except ValueError:
                return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

        if date_fin:
            try:
                date_obj = datetime.strptime(date_fin, '%Y-%m-%d').date()
                query += " AND c.date_commande <= %s"
                params.append(date_obj)
            except ValueError:
                return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400
            
        if montant_min:
            query += " AND c.montant >= %s"
            params.append(float(montant_min))
        
        if montant_max:
            query += " AND c.montant <= %s"
            params.append(float(montant_max))

        if ref_commande:
            query += " AND c.ref_commande = %s"
            params.append(ref_commande)
        if nom_article:
            query += " AND a.nom like %s"
            params.append(nom_article +'%')
        if sort_by:
            if sort_order.lower() == 'desc':
                query += " ORDER BY c.{} DESC".format(sort_by)
            else:
                query += " ORDER BY c.{} ASC".format(sort_by)

        cursor.execute(query, params)
        orders = cursor.fetchall()

        
        column_order = ["id", "ref_commande", "date_commande", "montant", "status"]
        result = []
        for row in orders:
            order = OrderedDict(zip(column_order, row))
            if order["date_commande"]:
                order["date_commande"] = order["date_commande"].isoformat()
            result.append(order)

        cursor.close()
        connection.close()

        if result:
            json_response = json.dumps(result, ensure_ascii=False, indent=4)
            return Response(json_response, mimetype='application/json'), 200
        else:
            return jsonify({"message": "Aucune commande trouvée pour ce client"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500

#done
################### recuperation d'une commande avec les articles en fonction de la reference de la commande #########

@app.route('/GetOrderDetails/<ref_commande>', methods=['GET'])
def GetOrderDetails(ref_commande):
    try:
        connection = getConnection()
        cursor = connection.cursor()
        columns = ["c.ref_commande","c.date_commande","c.montant","c.status"]
        query = f"""
        select {', '.join(columns)}
        from commande c
        where c.id = %s
        """
        cursor.execute(query, (ref_commande,))
        order = cursor.fetchone()
        if order:
            order_columns = [col.split(' AS ')[-1] if ' AS ' in col else col.split('.')[-1] for col in columns]
            order_details = OrderedDict(zip(order_columns, order))
            if order_details["date_commande"]:
                order_details["date_commande"] = order_details["date_commande"].isoformat()
            
            query_article = """
            select a.id,  a.ref_article, a.nom, ca.quantite, ca.prix
            from article a
            join commande_article ca on ca.id_article = a.id
            where ca.id_commande = %s
            """
            params = [ref_commande]
            cursor.execute(query_article, tuple(params))
            articles = cursor.fetchall()
            articles_list = [OrderedDict(zip(["id","ref_article","nom","quantite","prix"], article)) for article in articles]

            response_data = {
                "order_details": order_details,
                "articles": articles_list
            }
            json_response = json.dumps(response_data, ensure_ascii=False, indent=4)
            return Response(json_response, mimetype='application/json'), 200
        else:
            return jsonify({"message": "commande non trouvé"}), 404

    except Exception as e:
        return jsonify({"message": str(e)}), 500
    finally:
        cursor.close()
        connection.close()

    #done
##################### recuperation de toutes les commandes avec leurs articles #####################

@app.route('/GetAllOrdersWithItems', methods=['GET'])  # à vérifier si je vais garder
def GetAllOrdersWithItems():
    try:
        connection = getConnection()
        cursor = connection.cursor()

        ref_commande = request.args.get('ref_commande')
        nom_article = request.args.get('nom_article')
        prix_min = request.args.get('prix_min')
        prix_max = request.args.get('prix_max')
        quantite_min = request.args.get('quantite_min')
        quantite_max = request.args.get('quantite_max')
        sort_by = request.args.get('sort_by')
        sort_order = request.args.get('sort_order', 'asc')

        
        query = """
        SELECT c.ref_commande, a.nom AS nom_article, ca.quantite, ca.prix
        FROM commande c
        LEFT JOIN commande_article ca ON c.id = ca.id_commande
        LEFT JOIN article a ON ca.id_article = a.id
        WHERE 1=1
        """

        params = []
        if ref_commande:
            query += " AND c.ref_commande like %s"
            params.append(ref_commande +'%')
        
        if nom_article:
            query += " AND a.nom LIKE %s"
            params.append(nom_article +'%')
        
        if prix_min:
            query += " AND ca.prix >= %s"
            params.append(prix_min)
        
        if prix_max:
            query += " AND ca.prix <= %s"
            params.append(prix_max)

        if quantite_min:
            query += " and ca.quantite >= %s"
            params.append(quantite_min)
        
        if quantite_max:
            query += " and ca.quantite <= %s"
            params.append(quantite_max)

        valid_sort_columns = ["ref_commande","nom_article", "quantite", "prix"]
        if sort_by in valid_sort_columns:
            if sort_order.lower() == "desc":
                query += " order by {} desc".format(sort_by)
            else:
                query += " order by {} asc".format(sort_by)

        cursor.execute(query, params)
        orders_data = cursor.fetchall()

        if not orders_data:
            return jsonify({"message": "Aucune commande trouvée"}), 404

        orders_dict = {}
        for row in orders_data:
            ref_commande = row[0]
            article_detail = {
                "article_nom": row[1],
                "quantite": row[2],
                "prix": row[3]
            }

            if ref_commande not in orders_dict:
                orders_dict[ref_commande] = {
                    "ref_commande": ref_commande,
                    "articles": []
                }

            if article_detail["article_nom"]:  
                orders_dict[ref_commande]["articles"].append(article_detail)

        result = list(orders_dict.values())

        cursor.close()
        connection.close()

        json_response = json.dumps(result, ensure_ascii=False, indent=4)
        return Response(json_response, mimetype='application/json'), 200

    except Error as e:
        return jsonify({"error": str(e)}), 500



#checked

@app.route('/GetUsers', methods=['GET'])
def getUsers():
    connection = getConnection()
    cursor = connection.cursor()

    # Pour les filtres
    nom = request.args.get("nom")
    prenom = request.args.get("prenom")
    type_user = request.args.get("type_user")
    email = request.args.get("email")
    tel = request.args.get('tel')
    company = request.args.get('company')
    rwaccess = request.args.get('rwaccess')
    sort_by = request.args.get('sort_by')
    sort_order = request.args.get('sort_order','asc')
    
    query = "select * from utilisateur"
    filtres = []
    params = []
    
    if nom:
        filtres.append("nom like %s")
        params.append(nom + '%')
    if prenom:
        filtres.append("prenom like %s")
        params.append(prenom + '%')

    if type_user:
        filtres.append("type_user = %s")
        params.append(type_user)
    if email:
        filtres.append("email = %s")
        params.append(email)
    if tel:
        filtres.append('tel like %s')
        params.append(tel + '%')
    
    if filtres:
        query += " where " + " and ".join(filtres)

    if sort_by:
        if sort_order.lower() == "desc":
            query += " order by {} desc".format(sort_by)
        else:
            query += " order by {} asc".format(sort_by)
    
    cursor.execute(query, params)

    rows = cursor.fetchall()
    users = []
    for row in rows:
        access_data = json.loads(row[6])
        user = {
            'id': row[0],
            'nom': row[1],
            'prenom': row[2],
            'type user': row[3],
            'email': row[4],
            'tel': row[5],
            'access': access_data
        }
        
        if company or rwaccess:
            user_found = False
            for a in access_data:
                if company and company.lower() in a['company'].lower():
                    user_found = True
                    break
                if rwaccess and rwaccess.lower() == a['rwaccess'].lower():
                    user_found = True
                    break
            if not user_found:
                continue
        
        users.append(user)
    
    cursor.close()
    connection.close()
    
    json_response = json.dumps(users, ensure_ascii=False, indent=4)
    return Response(json_response, mimetype='application/json'), 200


@app.route('/AddUser', methods=['POST'])
def addUser():
    data = request.json  
    
    
    nom = data.get('nom')
    prenom = data.get('prenom')
    type_user = data.get('type_user').lower() if data.get('type_user') else None
    email = data.get('email')
    tel = data.get('tel')
    access = data.get('access')  
    
    if not nom or not prenom or not type_user or not email or not tel or not access:
        return jsonify({"error": "Tous les champs sont requis"}), 400

    
    if type_user not in ["user", "admin", "super admin"]:
        return jsonify({"error": "type_user doit être 'user', 'admin', ou 'super admin'"}), 400

    
    access_json = json.dumps(access)
    
    
    connection = getConnection()
    cursor = connection.cursor()
    
    # Préparer la requête d'insertion
    query = """
    INSERT INTO utilisateur (nom, prenom, type_user, email, tel, access)
    VALUES (%s, %s, %s, %s, %s, %s)
    """
    params = (nom, prenom, type_user, email, tel, access_json)
    
    try:
        cursor.execute(query, params)
        connection.commit()
        new_user_id = cursor.lastrowid
    except Exception as e:
        connection.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        connection.close()
    
    # Retourner la réponse avec l'ID du nouvel utilisateur
    return jsonify({"message": "Utilisateur ajouté avec succès", "user_id": new_user_id}), 201


@app.route('/UpdateUser/<int:user_id>', methods=['PUT'])
def updateUser(user_id):
    data = request.json  # On suppose que les données sont envoyées en format JSON
    
    # Récupérer les données de la requête
    nom = data.get('nom')
    prenom = data.get('prenom')
    type_user = data.get('type_user').lower() if data.get('type_user') else None
    email = data.get('email')
    tel = data.get('tel')
    access = data.get('access')  # Ce champ doit être un JSON valide
    
    # Connexion à la base de données
    connection = getConnection()
    cursor = connection.cursor()
    
    # Vérifier si l'utilisateur existe
    cursor.execute("SELECT * FROM utilisateur WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    if not user:
        return jsonify({"error": "Utilisateur non trouvé"}), 404

    # Construction de la requête de mise à jour
    update_fields = []
    params = []

    if nom:
        update_fields.append("nom = %s")
        params.append(nom)
    if prenom:
        update_fields.append("prenom = %s")
        params.append(prenom)
    if type_user:
        if type_user not in ["user", "admin", "super admin"]:
            return jsonify({"error": "type_user doit être 'user', 'admin', ou 'super admin'"}), 400
        update_fields.append("type_user = %s")
        params.append(type_user)
    if email:
        update_fields.append("email = %s")
        params.append(email)
    if tel:
        update_fields.append("tel = %s")
        params.append(tel)
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
        connection.commit()
    except Exception as e:
        connection.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        connection.close()
    
    return jsonify({"message": "Utilisateur mis à jour avec succès"}), 200



@app.route('/DeleteUser/<int:user_id>', methods=['DELETE'])
def deleteUser(user_id):
    # Connexion à la base de données
    connection = getConnection()
    cursor = connection.cursor()

    # Vérifier si l'utilisateur existe avant de le supprimer
    cursor.execute("SELECT * FROM utilisateur WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    if not user:
        return jsonify({"error": "Utilisateur non trouvé"}), 404

    # Préparer la requête de suppression
    query = "DELETE FROM utilisateur WHERE id = %s"
    
    try:
        cursor.execute(query, (user_id,))
        connection.commit()
    except Exception as e:
        connection.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cursor.close()
        connection.close()
    
    return jsonify({"message": "Utilisateur supprimé avec succès"}), 200



if __name__ == "__main__":
    #test_connection()
   # getCompanies()
    app.run(debug=True)
    #createDataBase("127.0.0.1", "root", "root","achref")  

