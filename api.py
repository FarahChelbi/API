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
        SELECT c.reference, c.nom, c.status, c.email, c.telephone, c.date_debut,c.date_fin,
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
            base_query += " AND c.date_debut >= %s"
            params.append(date_obj)
        except ValueError as e:
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400
    
    if date_fin:
        try:
            date_obj = datetime.strptime(date_fin, '%Y-%m-%d').date()
            base_query += " AND c.date_fin <= %s"
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
            'date_debut': row[5].isoformat() if row[5] else None,
            'date_fin': row[6].isoformat() if row[5] else None,
            'evaluation': row[7],
            'secteur': row[8],
            'ville': row[9],
            'nom_entreprise': row[10]
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

        columns = ["c.nom", "c.status", "c.email", "c.telephone", "c.tel2", "c.tel3", "c.fax", "c.site_web", "c.date_debut", "c.date_fin", "c.evaluation", "c.secteur", "c.adr_ligne1", "c.adr_ligne2", "c.code_postal", "c.ville", "c.pays", "c.info_personnelles", "c.preference", "c.decision", "c.visite", "comp.nom AS nom_entreprise"]
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

            if client_details["date_debut"]:
                client_details["date_debut"] = client_details["date_debut"].isoformat()
            if client_details["date_fin"]:
                client_details["date_fin"] = client_details["date_fin"].isoformat()

            query_contacts = """
            SELECT nom, prenom, fonction, tel1, tel2, tel3, fax, email, adr_ligne1, adr_ligne2, code_postal, ville, pays, site_web
            FROM contact
            WHERE ref_client = %s
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


@app.route('/GetOrders/<reference>', methods=['GET'] )
def GetOrders(reference):
    try:
        connection = getConnection()
        cursor = connection.cursor()
        #partie filtres***
        status = request.args.get("status")
        date_debut = request.args.get("date_debut")
        date_fin = request.args.get("date_fin")
        montant_min = request.args.get("montant_min")
        montant_max = request.args.get("montant_max")
        article = request.args.get("article")


        #columns = ["a.id_article as nom_article" ," c.date_debut", "c.date_fin", "c.montant", "c.status", "c.quantite"]
        #query = "select * from commande where ref_client = %s"
        query = """
        SELECT commande.id, commande.ref_client, article.nom AS article_nom, commande.date_debut, 
               commande.date_fin, commande.montant, commande.status, commande.quantite
        FROM commande
        JOIN article ON commande.id_article = article.id
        WHERE commande.ref_client = %s
        """
        params = [reference]
        if status:
            query += " AND commande.status = %s"
            params.append(status)
        
        if date_debut:
            try:
                date_obj = datetime.strptime(date_debut, '%Y-%m-%d').date()
                query += " AND commande.date_debut >= %s"
                params.append(date_obj)
            except ValueError as e:
                return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400

        if date_fin:
            try:
                date_obj = datetime.strptime(date_fin, '%Y-%m-%d').date()
                query += " AND commande.date_fin <= %s"
                params.append(date_obj)
            except ValueError as e:
                return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400
            
        if montant_min:
            query += " AND commande.montant >= %s"
            params.append(float(montant_min))
        
        if montant_max:
            query += " AND commande.montant <= %s"
            params.append(float(montant_max))

        if article:
            query += " AND article.nom like %s"
            params.append(article +'%')



        cursor.execute(query,params)
        orders = cursor.fetchall()
        column_order = ["id", "ref_client", "article_nom", "date_debut", "date_fin", "montant", "status", "quantite"]

        result = []
        for row in orders:
            order = OrderedDict(zip(column_order, row))
            if order["date_debut"]:
                order["date_debut"] = order["date_debut"].isoformat()
            if order["date_fin"]:
                order["date_fin"] = order["date_fin"].isoformat()
            result.append(order)

        cursor.close()
        connection.close()

        if result:
            #return jsonify(result), 200
            json_response = json.dumps(result, ensure_ascii=False, indent=4)
            return Response(json_response, mimetype='application/json'), 200
        else:
            return jsonify({"message": "aucune commande trouvee pour ce client"}), 404

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
    #cursor.execute("select nom, prenom, email from utilisateur;")
    query = "select nom, prenom, email from utilisateur"
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
    
    if filtres:
        query += " where " +" and ".join(filtres)
    
    cursor.execute(query, params)


    rows = cursor.fetchall()
    users = []
    for row in rows:
        user = {
            'nom' : row[0],
            'prenom': row[1],
            'email' : row[2]
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

