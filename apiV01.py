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
    nom_entreprise = request.args.get('nom_entreprise')
    connection = test_connection()
    cursor = connection.cursor()
    
    base_query = "SELECT * FROM companies"
    params = []
    
    if nom_entreprise:
        base_query += " WHERE nom LIKE %s"
        params.append(f"{nom_entreprise}%")
    
    if sort_order:
        if sort_order.lower() == 'desc':
            base_query += " ORDER BY nom DESC"
        elif sort_order.lower() == 'asc':
            base_query += " ORDER BY nom ASC"
    
    cursor.execute(base_query, tuple(params))
    
    rows = cursor.fetchall()
    companies = [{'nom': row[1]} for row in rows]
    
    cursor.close()
    connection.close()
    
    return jsonify(companies)


"""@app.route('/GetCompaniesWithId', methods=['GET']) # 2eme cas si on veux les id
def getCompanies2():
    connection = test_connection()
    cursor = connection.cursor()
    cursor.execute("select * from companies")
    rows = cursor.fetchall()
    #companies = [{'nom': row[1]} for row in rows]
    companies = [{'id': row[0], 'nom': row[1]} for row in rows]
    cursor.close()
    connection.close()
    return jsonify(companies) """



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

    evaluation = request.args.get("evaluation")
    secteur = request.args.get("secteur")
    ville = request.args.get("ville")

    sort_by = request.args.get('sort_by')
    sort_order = request.args.get('sort_order','asc') 
    
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
        base_query += " AND c.reference like %s"
        params.append(reference +'%')
    
    if nom:
        base_query += "AND c.nom LIKE %s"
        params.append(nom +'%')
    if status:
        base_query += "AND c.status like %s"
        params.append(status +'%')
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
    if evaluation:
        base_query += "AND c.evaluation like %s"
        params.append(evaluation +'%')
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
        WHERE c.reference = %s
        """
        cursor.execute(query, (reference,))
        client = cursor.fetchone()

        if client:
            client_columns = [col.split(' AS ')[-1] if ' AS ' in col else col.split('.')[-1] for col in columns]
            client_details = OrderedDict(zip(client_columns, client))

            
            if client_details["date_derniere_commande"]:
                client_details["date_derniere_commande"] = client_details["date_derniere_commande"].isoformat()

            
            contact_filters = {
                "nom": request.args.get('contact_nom'),
                "prenom": request.args.get('contact_prenom'),
                "fonction": request.args.get('contact_fonction'),
                "ville": request.args.get('contact_ville'),
                "pays": request.args.get('contact_pays'),
                "code_postal": request.args.get('contact_code_postal'),
                "email": request.args.get('contact_email'),
                "fax": request.args.get('contact_fax')
            }
            contact_tel = request.args.get('contact_tel')
            sort_by = request.args.get('sort_by')
            sort_order = request.args.get('sort_order')

            query_contacts = """
            SELECT c.nom, c.prenom, c.fonction, c.tel1, c.tel2, c.tel3, c.fax, c.email, c.adr_ligne1, c.adr_ligne2, c.code_postal, c.ville, c.pays, c.site_web
            FROM contact c
            JOIN clients cl ON c.ref_client = cl.id
            WHERE cl.reference = %s
            """
            params = [reference]

            
            for key, value in contact_filters.items():
                if value:
                    query_contacts += " AND c.{} LIKE %s".format(key)
                    params.append(value +'%')

            if contact_tel:   #contact_tel est le filtre pour les 3 num tel
                query_contacts += " AND (c.tel1 LIKE %s OR c.tel2 LIKE %s OR c.tel3 LIKE %s)"
                params.extend([f'{contact_tel}%', f'{contact_tel}%', f'{contact_tel}%'])

            if sort_by:
                if sort_order.lower() == "desc":
                    query_contacts += " ORDER BY c.{} DESC".format(sort_by)
                else:
                    query_contacts += " ORDER BY c.{} ASC".format(sort_by)

            
            
            cursor.execute(query_contacts, tuple(params))
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
        sort_by = request.args.get('sort_by')
        sort_order = request.args.get('sort_order','asc')

        query = """
        SELECT c.ref_commande, c.date_commande, 
               c.montant, c.status, cl.reference AS client
        FROM commande c
        JOIN clients cl ON c.ref_client = cl.id
        WHERE cl.reference = %s
        """
        params = [reference]

        if status:
            query += " AND c.status like %s"
            params.append(status + '%')
        
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
            query += " AND c.ref_commande LIKE %s"
            params.append(ref_commande + '%')
        if sort_by:
            if sort_order.lower() == 'desc':
                query += " ORDER BY c.{} DESC".format(sort_by)
            else:
                query += " ORDER BY c.{} ASC".format(sort_by)

        cursor.execute(query, params)
        orders = cursor.fetchall()

        
        column_order = ["ref_commande", "date_commande", "montant", "status", "client"]

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

        # liste des filtres
        nom_article = request.args.get('nom_article')
        quantite_min = request.args.get('quantite_min')
        quantite_max = request.args.get('quantite_max')
        prix_min = request.args.get('prix_min')
        prix_max = request.args.get('prix_max')
        sort_by = request.args.get('sort_by')
        sort_order = request.args.get('sort_order','asc')

        connection = getConnection()
        cursor = connection.cursor()

        query = """
        SELECT c.ref_commande, a.nom AS nom_article, ca.quantite, ca.prix
        FROM commande_article ca
        JOIN commande c ON ca.id_commande = c.id
        JOIN article a ON ca.id_article = a.id
        WHERE c.ref_commande = %s
        """
        params = [ref_commande]
        if nom_article:
            query += " and a.nom like %s"
            params.append(nom_article +'%')
        
        if quantite_min:
            query += " and ca.quantite >= %s"
            params.append(quantite_min)
        if quantite_max:
            query += " and ca.quantite <= %s"
            params.append(quantite_max)
        
        if prix_min:
            query += " and ca.prix >= %s"
            params.append(prix_min)
        if prix_max:
            query += " and ca.prix <= %s"
            params.append(prix_max)

        valid_sort_columns = ["nom_article", "quantite", "prix"]
        if sort_by in valid_sort_columns:
            if sort_order.lower() == "desc":
                query += " order by {} desc".format(sort_by)
            else:
                query += " order by {} asc".format(sort_by)

        cursor.execute(query, tuple(params))
        #cursor.execute(query, [ref_commande])
        order_details = cursor.fetchall()

        if not order_details:
            return jsonify({"message": "Aucun article trouvé pour cette commande"}), 404

        column_order = ["ref_commande", "nom_article", "quantite", "prix"]
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
    
    #done
##################### recuperation de toutes les commandes avec leurs articles #####################
@app.route('/GetAllOrdersWithItems', methods=['GET'])
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
    if email:
        filtres.append("email like %s")
        params.append(email + '%')
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
        access_data = json.loads(row[5])  
        if company or rwaccess:
            company_filtered = []
            for a in access_data:
                if company and company.lower() in a['company'].lower():
                    if rwaccess:
                        if a['rwaccess'].lower() == rwaccess.lower():
                            company_filtered.append(a)
                    else:
                        company_filtered.append(a)
                elif rwaccess and not company:
                    if a['rwaccess'].lower() == rwaccess.lower():
                        company_filtered.append(a)
            if not company_filtered:
                continue
        else:
            company_filtered = access_data
  
        user = {
            'nom': row[1],
            'prenom': row[2],
            'email': row[3],
            'tel': row[4],
            'access': company_filtered
        }
        users.append(user)
    
    cursor.close()
    connection.close()
    
    json_response = json.dumps(users, ensure_ascii=False, indent=4)
    return Response(json_response, mimetype='application/json'), 200


if __name__ == "__main__":
    #test_connection()
   # getCompanies()
    app.run(debug=True)
    #createDataBase("127.0.0.1", "root", "root","achref")  

