from bson import ObjectId
from app import mongo
from app import RESOLVED_PERMISSIONS


def get_unpaginated_client_users(departament_id):
    """generates the list of all clients as a drop down
    """
    client_users_list = list(mongo.client_user.find({
        "departament_id": departament_id
    }))
    client_users_list = dereference_client_users_allowed_actions_for_client(client_users_list)
    client_users_list = dereference_client_users_allowed_cost_centers_for_client(client_users_list, departament_id)
    client_users_list = [{
        "id": str(client_user['_id']),
        'firstname': client_user['first_name'],
        'lastname': client_user['last_name'],
        'email': client_user['email'],
        'user_role_details': dereference_client_users_role_for_client(client_user['_id']),
        'usertype': client_user.get('role', "Administrator"),
        "is_admin": client_user.get('is_admin', False),
        'activated': client_user.get('activated', False),
        'allowed_actions': client_user.get('allowed_actions', list()),
        'allowed_cost_centers': client_user.get('allowed_cost_centers')} for client_user in client_users_list]
    resp = {
        "clients": client_users_list
    }
    return resp


def dereference_client_users_allowed_actions_for_client(client_users_list):
    # Get all client's api_users in one query
    # Map client_user _id: api_user
    # Extract all referenced permissions
    cu_ids = [cu['_id'] for cu in client_users_list]
    api_users = mongo.api_users.find({'client_user': {'$in': cu_ids}})

    permission_ids = list()
    cu_api_user_map = dict()
    for au in api_users:
        if au.get("user_role"):
            for r in au.get("user_role"):
                roles = mongo.roles.find_one({'_id': r, 'enabled': True})
                if roles:
                    permission_ids += roles.get('permission', list())
        permission_ids += au.get('permissions', list())
        cu_api_user_map[au.get('client_user')] = au

    # Try to get routes _ids resolved and mapped to permissions from global variable
    route_ids = list()
    for pid in permission_ids:
        route_ids += RESOLVED_PERMISSIONS.get(pid, list())

    # Query for all relevant routes and remap them route_id: route
    routes = list(mongo.routes.find({'_id': {'$in': route_ids}}))
    route_id_route_map = {r['_id']: r for r in routes}

    # Query for all relevant permissions and remap them permission_id: permission
    # Extract all referenced routines
    relevant_permissions = list(mongo.permissions.find({'_id': {'$in': permission_ids}}))
    permission_id_permission_map = dict()
    for p in relevant_permissions:
        permission_id_permission_map[p['_id']] = p

    # Go over client_users list and put whole dereferenced permissions, routes, routines structure under allowed actions

    dereferenced_permissions = dict()
    role_permission = list()
    for cu in client_users_list:
        allowed_actions = list()
        au = cu_api_user_map.get(cu['_id'])
        if not au:
            cu['error'] = "No API_User wrapper found, can't resolve allowed_actions"
            cu['allowed_actions'] = list()
            continue
        permissions = au.get('permissions', list())
        if "user_role" in au:
            roles = mongo.roles.find({'_id': {'$in': au['user_role']}, 'enabled': True})
            for r in roles:
                permissions += r.get('permission', list())
                role_permission += r.get('permission', list())

        for pid in permissions:
            if pid in dereferenced_permissions:
                allowed_actions.append(dereferenced_permissions[pid])
                continue
            p = permission_id_permission_map.get(pid)
            if not p:
                # Broken reference to permission object. Put an empty object there
                p = {'_id': pid, 'routes': [], 'routines': [], 'error': 'Invalid reference', 'ui_aliases': []}
                allowed_actions.append(p)
                continue
            allowed_actions.append(p)
            # Exctract ui_aliases (if any) from routes and propagate them up to permission level
            p['ui_aliases'] = set()
            deref_routes = list()
            for r_id in p.get('routes', list()):
                route = route_id_route_map[r_id]
                deref_routes.append(route)
                if 'ui_aliases' in route:
                    p['ui_aliases'].update(route['ui_aliases'])

            p['role_based'] = False
            if pid in role_permission:
                p['role_based'] = True

            p['routes'] = deref_routes
            p['routines'] = []
            p['ui_aliases'] = list(p['ui_aliases'])
            dereferenced_permissions[pid] = p

        allowed_actions.sort(key=lambda p: p.get('name', 'z'))
        cu['allowed_actions'] = allowed_actions

    return client_users_list


def dereference_client_users_allowed_cost_centers_for_client(cu_list, departament_id):
    ccs = mongo.cost_centers.find({'departament_id': departament_id, 'is_active': True})
    index = {cc['_id']: cc for cc in ccs}
    for cu in cu_list:
        allowed_cost_centers = cu.get('allowed_cost_centers', list())
        allowed_cost_centers_expanded = list()
        for cc_id in allowed_cost_centers:
            allowed_cost_centers_expanded.append(dict(name=index[cc_id]['name'], _id=index[cc_id]['_id']))
        cu['allowed_cost_centers'] = allowed_cost_centers_expanded
    return cu_list


def dereference_client_users_role_for_client(client_user_id):
    role = list()
    api_user = mongo.api_users.find_one({'client_user': ObjectId(client_user_id)})
    if api_user.get('user_role'):
        for r in api_user.get('user_role'):
            role_data = mongo.roles.find_one({'_id': r, 'enabled': True})
            if role_data:
                role.append(role_data)
    return role
