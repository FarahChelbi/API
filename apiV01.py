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


@app.route('/GetCompanies', methods=['GET'])  
def getCompanies():
    #connection = getConnection()
    connection = test_connection()
    cursor = connection.cursor()
    cursor.execute("select * from companies")
    rows = cursor.fetchall()
    companies = [{'nom': row[1]} for row in rows]
    cursor.close()
    connection.close()
    return jsonify(companies)

@app.route('/GetCompaniesWithId', methods=['GET']) # 2eme cas si on veux les id
def getCompanies2():
    connection = test_connection()
    cursor = connection.cursor()
    cursor.execute("select * from companies")
    rows = cursor.fetchall()
    #companies = [{'nom': row[1]} for row in rows]
    companies = [{'id': row[0], 'nom': row[1]} for row in rows]
    cursor.close()
    connection.close()
    return jsonify(companies) 





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

    evaluation = request.args.get("evaluation")
    secteur = request.args.get("secteur")
    ville = request.args.get("ville")

    sort_by = request.args.get('sort_by','nom') # critere pas defaut
    sort_order = request.args.get('sort_order','asc') #aussi
    
    if not nom_entreprise:
        return jsonify({"error": "nom_entreprise parameter is required"}), 400
    
    connection = getConnection()
    cursor = connection.cursor()
    
    
    base_query = """
        SELECT c.reference, c.nom, c.status, c.email, c.telephone, c.date_derniere_commande,
               c.evaluation, c.secteur, c.ville, comp.nom AS nom_entreprise
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
        base_query += "AND c.telephone = %s"
        params.append(telephone)
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
    if evaluation:
        base_query += "AND c.evaluation = %s"
        params.append(evaluation)
    if secteur:
        base_query += "AND c.secteur = %s"
        params.append(secteur)
    if ville:
        base_query += "AND c.ville = %s"
        params.append(ville)

    if sort_order.lower() == 'desc':
        base_query += " ORDER BY c.{} DESC".format(sort_by)
    else:
        base_query += " ORDER BY c.{} ASC".format(sort_by)
    
    cursor.execute(base_query, tuple(params))
    rows = cursor.fetchall()
    
    clients = []
    
    for row in rows:
        client = {
            'reference': row[0],
            'nom': row[1],
            'status': row[2],
            'email': row[3],
            'telephone': row[4],
            'date_derniere_commande': row[5].isoformat() if row[5] else None,
            'evaluation': row[6],
            'secteur': row[7],
            'ville': row[8],
            'nom_entreprise': row[9]
        }
        clients.append(client)
        
    
    cursor.close()
    connection.close()
    json_response = json.dumps(clients, ensure_ascii=False, indent=4)
    return Response(json_response, mimetype='application/json'), 200
    #return jsonify(clients)



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
        WHERE c.reference = %s
        """
        cursor.execute(query, (reference,))
        client = cursor.fetchone()

        if client:
            client_columns = [col.split(' AS ')[-1] if ' AS ' in col else col.split('.')[-1] for col in columns]
            client_details = OrderedDict(zip(client_columns, client))

            if client_details["date_derniere_commande"]:
                client_details["date_derniere_commande"] = client_details["date_derniere_commande"].isoformat()
           
            query_contacts = """
            SELECT c.nom, c.prenom, c.fonction, c.tel1, c.tel2, c.tel3, c.fax, c.email, c.adr_ligne1, c.adr_ligne2, c.code_postal, c.ville, c.pays, c.site_web
            FROM contact c
            JOIN clients cl ON c.ref_client = cl.id
            WHERE cl.reference = %s
            """
            cursor.execute(query_contacts, (reference,))
            contacts = cursor.fetchall()
            contacts_list = [OrderedDict(zip(["nom", "prenom", "fonction", "tel1", "tel2", "tel3", "fax", "email", "adr_ligne1", "adr_ligne2", "code_postal", "ville", "pays", "site_web"], contact)) for contact in contacts]

            response_data = {
                "client_details": client_details,
                "contacts": contacts_list
            }

            json_response = json.dumps(response_data, ensure_ascii=False, indent=4)
            return Response(json_response, mimetype='application/json'), 200
        else:
            return jsonify({"message": "Client non trouvé"}), 404
    except Exception as e:
        # En cas d'erreur, retournez un message d'erreur approprié
        return jsonify({"message": str(e)}), 500
    finally:
        cursor.close()
        connection.close()


@app.route('/GetOrders/<reference>', methods=['GET'])
def GetOrders(reference):
    try:
        connection = getConnection()
        cursor = connection.cursor()

        # Partie filtres
        status = request.args.get("status")
        date_debut = request.args.get("date_debut")
        date_fin = request.args.get("date_fin")
        montant_min = request.args.get("montant_min")
        montant_max = request.args.get("montant_max")
        ref = request.args.get("ref")

        # Requête SQL avec jointure sur `clients` pour filtrer par `reference` du client
        query = """
        SELECT c.id, c.ref_commande, c.date_commande, 
               c.montant, c.status, c.ref_client
        FROM commande c
        JOIN clients cl ON c.ref_client = cl.id
        WHERE cl.reference = %s
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

        if ref:
            query += " AND c.ref_commande LIKE %s"
            params.append(ref + '%')

        cursor.execute(query, params)
        orders = cursor.fetchall()
        column_order = ["id", "ref_commande", "date_commande", "montant", "status", "ref_client"]

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
            return jsonify({"message": "aucune commande trouvée pour ce client"}), 404

    except Error as e:
        return jsonify({"error": str(e)}), 500
    


################### recuperation d'une commande avec les articles en fonction de la reference de la commande #########
@app.route('/GetOrderDetails/<ref_commande>', methods=['GET'])
def GetOrderDetails(ref_commande):
    try:
        connection = getConnection()
        cursor = connection.cursor()

        query = """
        SELECT c.ref_commande, a.nom AS article_nom, ca.quantite, ca.prix
        FROM commande_article ca
        JOIN commande c ON ca.id_commande = c.id
        JOIN article a ON ca.id_article = a.id
        WHERE c.ref_commande = %s
        """
        cursor.execute(query, [ref_commande])
        order_details = cursor.fetchall()

        if not order_details:
            return jsonify({"message": "Aucun article trouvé pour cette commande"}), 404

        column_order = ["ref_commande", "article_nom", "quantite", "prix"]
        result = []
        for row in order_details:
            order_detail = OrderedDict(zip(column_order, row))
            result.append(order_detail)

        cursor.close()
        connection.close()

        json_response = json.dumps(result, ensure_ascii=False, indent=4)
        return Response(json_response, mimetype='application/json'), 200

    except Error as e:
        return jsonify({"error": str(e)}), 500
    
##################### recuperation de toutes les commandes avec leurs articles #####################
@app.route('/GetAllOrdersItems', methods=['GET'])
def GetAllOrdersItems():
    try:
        connection = getConnection()
        cursor = connection.cursor()

        query = """
        SELECT c.ref_commande, a.nom AS article_nom, ca.quantite, ca.prix
        FROM commande c
        LEFT JOIN commande_article ca ON c.id = ca.id_commande
        LEFT JOIN article a ON ca.id_article = a.id
        """
        cursor.execute(query)
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




@app.route('/GetUsers', methods=['GET'])
def getUsers():
    connection = getConnection()
    cursor = connection.cursor()

    # pour les filtres
    nom = request.args.get("nom")
    prenom = request.args.get("prenom")
    email = request.args.get("email")
    tel = request.args.get('tel')
    company = request.args.get('company')
    
    #cursor.execute("select nom, prenom, email from utilisateur;")
    #query = "select nom, prenom, email from utilisateur"
    query = "select * from utilisateur"
    filtres = []
    params = []
    
    if nom:
        filtres.append("nom = %s")
        params.append(nom)
    if prenom:
        filtres.append("prenom = %s")
        params.append(prenom)
    if email:
        filtres.append("email = %s")
        params.append(email)
    if tel:
        filtres.append('tel= %s')
        params.append(tel)
    
    if filtres:
        query += " where " +" and ".join(filtres)
    
    cursor.execute(query, params)


    rows = cursor.fetchall()
    users = []
    for row in rows:
        access_data = json.loads(row[5])  
        if company:
            
            #company_filtered = [item for item in access_data if item.get('company') == company]
            company_filtered = [a for a in access_data if company.lower() in a['company'].lower()]
            if not company_filtered:
                continue  
        else:
            company_filtered = access_data
  
        user = {
            'nom' : row[1],
            'prenom': row[2],
            'email' : row[3],
            'tel' : row[4],
            'access': company_filtered
        }
        users.append(user)
    cursor.close()
    connection.close()
    #return jsonify(users)
    json_response = json.dumps(users, ensure_ascii=False, indent=4)
    return Response(json_response, mimetype='application/json'), 200





if __name__ == "__main__":
    #test_connection()
   # getCompanies()
    app.run(debug=True)
    #createDataBase("127.0.0.1", "root", "root","achref")  

