import json
from bson import json_util, ObjectId
from flask import Response
from app import api
import business


@api.route("/list_client_user/<departament_id>", methods=['GET'])
def get_client_users(departament_id):
    """gets all the client_user list
    """
    try:
        response = business.get_unpaginated_client_users(ObjectId(departament_id))
    except Exception as e:
        response = {"status": False, "message": "Error {}".format(str(e))}
    return Response(json.dumps(response, default=json_util.default), mimetype="application/json")
