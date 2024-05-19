# app.py
from flask import Flask, jsonify, request
from pymongo import MongoClient
from bson import ObjectId
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re

app = Flask(__name__)

# MongoDB Atlas connection
client = MongoClient(
    'mongodb+srv://truong:LdTZURx0amyAPAZW@itemsandstaffs.i9nkc3d.mongodb.net/?retryWrites=true&w=majority&appName=ItemsAndStaffs')
db = client.get_database('monday-data')


class tools:
    def remove_ids(document):
        """
        Recursively remove '_id' and 'id' fields from the document.
        """
        if isinstance(document, dict):
            # Create a new dictionary without '_id' or 'id' keys
            return {k: tools.remove_ids(v) for k, v in document.items() if k not in ['_id', 'id']}
        elif isinstance(document, list):
            # Recursively process each item in the list
            return [tools.remove_ids(i) for i in document]
        else:
            return document

    def convert_objectid_to_str(document):
        """
        Recursively convert ObjectId to string in the document.
        """
        if isinstance(document, dict):
            return {k: tools.convert_objectid_to_str(v) for k, v in document.items()}
        elif isinstance(document, list):
            return [tools.convert_objectid_to_str(i) for i in document]
        elif isinstance(document, ObjectId):
            return str(document)
        else:
            return document

    def create_description(document):
        description = []
        for key, value in document.items():
            if key not in ['_id', 'id']:
                if isinstance(value, dict):
                    description.append(tools.create_description(value))
                elif isinstance(value, list):
                    description.extend(
                        [str(v) for v in value if not isinstance(v, (dict, list))])
                else:
                    description.append(str(value))
        return ' '.join(description)

    def remove_leading_number(text):
        # Use regex to match and remove leading number followed by a dot and space
        new_text = re.sub(r'^\d+\. ', '', text)
        return new_text

    def process_documents(documents):
        processed = []
        for doc in documents:
            description = tools.create_description(doc)
            doc['description'] = description
            processed.append(doc)
        return processed


class mongoDataRetrieval:
    def get_all_data(search_type):
        print("Start getting search base!")

        if search_type == 'contact':
            print('start getting all items...')
            all_data = db['contacts'].find(
                {}, {'client_code': 1, 'client_information': 1, '_id': 0})
            print('finish get all items!')
            all_contacts_description = tools.process_documents(all_data)
            return all_contacts_description

        elif search_type == 'business':
            print('start getting all items...')
            all_data = db['business clients'].find(
                {}, {'business_code': 1, 'business_name': 1, 'business_information': 1, '_id': 0})
            print('finish get all items!')
            all_business_description = tools.process_documents(all_data)
            return all_business_description

        elif search_type == 'group':
            print('start getting all items...')
            all_data = db['groups clients'].find(
                {}, {'group_code': 1, 'contact': 1, 'business': 1, '_id': 0})
            print('finish get all items!')
            all_groups_description = tools.process_documents(all_data)
            return all_groups_description

        elif search_type == 'task':
            print('start getting all items...')
            all_data = db['all-task-items'].find(
                {}, {'name': 1, 'group': 1, 'board': 1, 'id': 1, '_id': 0})
            print('finish get all items!')
            all_items_description = tools.process_documents(all_data)
            return all_items_description

        elif search_type == 'employee':
            print('start getting all items...')
            all_data = db['company employee'].find({}, {'name': 1, '_id': 0})
            print('finish get all items!')
            all_groups_description = tools.process_documents(all_data)
            return all_groups_description


def find_best_match(search_query, search_results, threshold=0.1):
    """
    Finds the best matching result based on a search query using TF-IDF and cosine similarity.

    Args:
    - search_query (str): The search query string.
    - search_results (list): A list of dictionaries containing search results.
    - threshold (float): Minimum similarity score to consider a match valid.

    Returns:
    - dict: The best matching result with its score.
    """
    documents = [search_query] + [result['description']
                                  for result in search_results if result is not None]

    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(documents)

    cosine_similarities = cosine_similarity(
        tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()

    best_match_index = np.argmax(cosine_similarities)
    best_match_score = cosine_similarities[best_match_index]

    if best_match_score >= threshold:
        best_match = search_results[best_match_index]
    else:
        best_match = {"message": "No suitable match found.",
                      "score": best_match_score}

    return best_match


def retrive_monday_data(search_type, search_query, search_for):

    if search_type in ['business', 'contact', 'group', 'employee', 'task']:

        search_base = mongoDataRetrieval.get_all_data(search_type=search_type)
        best_choice = find_best_match(
            search_query=search_query, search_results=search_base)

        if search_type == 'contact':

            client_code = str(best_choice["client_code"])
            client_name = str(best_choice["client_information"]['name'])

            data = {
                'client code': client_code,
                'name': client_name
            }

            if search_for == 'information':
                data['infomation'] = best_choice['client_information']

            elif search_for == 'tasks related':
                client_data = db['contacts'].find_one(
                    {"client_code": client_code})

                if 'DAGs' in client_data:
                    data['tasks'] = client_data['DAGs']

                    item_ids = [str(item['id'])
                                for board in data['tasks'].values() for item in board]
                    items_from_db = list(
                        db['all-task-items'].find({'id': {'$in': item_ids}}))
                    items_dict = {item['id']: item for item in items_from_db}

                    for board, items in data['tasks'].items():
                        for i, item in enumerate(items):
                            item_id = str(item['id'])
                            if item_id in items_dict:
                                items[i] = items_dict[item_id]

                else:
                    data['tasks'] = {}

            data = tools.remove_ids(data)

            return data

        elif search_type == 'business':

            business_code = str(best_choice["business_code"])
            business_name = str(best_choice['business_name'])

            data = {
                'business code': business_code,
                'business name': business_name
            }

            if search_for == 'information':
                data['infomation'] = best_choice['business_information']

            elif search_for == 'tasks related':
                business_data = db['business clients'].find_one(
                    {"business_code": business_code})

                if 'DAGs' in business_data:
                    data['tasks'] = business_data['DAGs']

                    item_ids = [str(item['id'])
                                for board in data['tasks'].values() for item in board]
                    items_from_db = list(
                        db['all-task-items'].find({'id': {'$in': item_ids}}))
                    items_dict = {item['id']: item for item in items_from_db}

                    for board, items in data['tasks'].items():
                        for i, item in enumerate(items):
                            item_id = str(item['id'])
                            if item_id in items_dict:
                                items[i] = items_dict[item_id]
                else:
                    data['tasks'] = {}

            data = tools.remove_ids(data)

            return data

        elif search_type == 'group':

            group_code = str(best_choice["group_code"])
            data = {
                'group name': group_code,
            }

            group_data = db['groups clients'].find_one(
                {"group_code": group_code})

            if search_for == 'information':
                data['infomation'] = {
                    'contacts': group_data['contact'],
                    'business': group_data['business']
                }

            elif search_for == 'tasks related':
                if 'general_admin_tasks' in group_data:
                    data['general admin tasks'] = group_data['general_admin_tasks']
                else:
                    data['general admin tasks'] = []

            data = tools.remove_ids(data)

            return data

        elif search_type == 'employee':

            employee_name = str(best_choice["name"])
            data = {
                'employee name': employee_name,
            }

            if search_for == 'today tasks':
                employee_data = db['company employee'].find_one(
                    {"name": employee_name})
                data['today tasks'] = {
                    "General Admin Task": employee_data['general_admin_tasks'],
                    "Individual Tax Return": employee_data['individual_tax_return'],
                    "Company Tax and FR": employee_data['company_tax_fr'],
                    "Trust Tax and FR": employee_data['trust_tax_fr'],
                    "Partnership Tax": employee_data['partnership_tax'],
                    "SMSF Tax and FR": employee_data['smsf_tax_fr'],
                    "Quarterly BAS": employee_data['quarterly_bas'],
                    "Monthly IAS": employee_data['monthly_ias'],
                    "Payroll": employee_data['payroll'],
                    "TPAR Lodgement": employee_data['tpar_lodgement'],
                }

            elif search_for == 'yesterday tasks':
                employee_data = db['employee yesterday'].find_one(
                    {"name": employee_name})
                data['yesterday tasks'] = {
                    "General Admin Task": employee_data['general_admin_tasks'],
                    "Individual Tax Return": employee_data['individual_tax_return'],
                    "Company Tax and FR": employee_data['company_tax_fr'],
                    "Trust Tax and FR": employee_data['trust_tax_fr'],
                    "Partnership Tax": employee_data['partnership_tax'],
                    "SMSF Tax and FR": employee_data['smsf_tax_fr'],
                    "Quarterly BAS": employee_data['quarterly_bas'],
                    "Monthly IAS": employee_data['monthly_ias'],
                    "Payroll": employee_data['payroll'],
                    "TPAR Lodgement": employee_data['tpar_lodgement'],
                }

            data = tools.remove_ids(data)

            return data

        elif search_type == 'task':
            task_board = str(best_choice["board"]['name'])
            task_group = str(best_choice["group"]['title'])
            task_name = tools.remove_leading_number(
                task_board) + ' - ' + task_group + ': ' + str(best_choice["name"])

            data = {
                'Task name': task_name,
            }

            task_data = db['all-task-items'].find_one(
                {"id": str(best_choice["id"])})

            if search_for == 'column values':
                data['column values'] = task_data['column_values']

            elif search_for == 'updates':
                data['updates'] = task_data['updates']

            data = tools.remove_ids(data)

            return data

    else:
        return {"Error": "Invalid search_type, try again!"}


@app.route('/api/v1/<collection_name>', methods=['GET', 'POST'])
def get_documents(collection_name):
    collection = db[collection_name]
    documents = list(collection.find())
    documents = [tools.convert_objectid_to_str(doc) for doc in documents]
    return jsonify(documents)


@app.route('/api/v1/retrieve_monday_data', methods=['POST'])
def retrieve_monday_data_api():
    data = request.json
    search_type = data.get('search_type')
    search_query = data.get('search_query')
    search_for = data.get('search_for')

    result = retrive_monday_data(search_type, search_query, search_for)
    return result


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8083)
