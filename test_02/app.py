import os
from flask import Flask
from pymongo import MongoClient


api = Flask(__name__)


def make_mongo(db_name=None):
    if db_name is None:
        try:
            db_name = api.config['DB_NAME']
        except KeyError:
            db_name = os.getenv("DB_NAME", "test_database")
    client = MongoClient(port=27017)
    return client[db_name]


mongo = make_mongo()
RESOLVED_PERMISSIONS = dict()


@api.before_first_request
def resolve_permissions():
    mongo = make_mongo()
    permissions = mongo['permissions'].find({'enabled': True})
    for permission in permissions:
        allowed_routes = permission.get('routes', [])
        routines = permission.get('routines', [])
        routines = mongo['routines'].find({'enabled': True, '_id': {'$in': routines}})
        for routine in routines:
            allowed_routes += routine.get('routes', [])
        RESOLVED_PERMISSIONS[permission['_id']] = allowed_routes
    mongo.client.close()


@api.teardown_appcontext
def close_db(error):
    """Closes the database again at the end of the request."""
    mongo.client.close()


@api.route('/')
def hello_world():
    return 'Hello World!'


from views import *


if __name__ == '__main__':
    api.run()
