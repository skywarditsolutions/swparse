ACCOUNT_LOGIN = "/api/access/login"
ACCOUNT_LOGOUT = "/api/access/logout"
ACCOUNT_REGISTER = "/api/access/signup"
ACCOUNT_PROFILE = "/api/me"
ACCOUNT_LIST = "/api/users"
ACCOUNT_DELETE = "/api/users/{user_id:uuid}"
ACCOUNT_DETAIL = "/api/users/{user_id:uuid}"
ACCOUNT_UPDATE = "/api/users/{user_id:uuid}"
ACCOUNT_CREATE = "/api/users"
ACCOUNT_ASSIGN_ROLE = "/api/roles/{role_slug:str}/assign"
ACCOUNT_REVOKE_ROLE = "/api/roles/{role_slug:str}/revoke"

API_KEY_GENERATE = "/api/keys/create"
API_KEY_LIST = "/api/keys/list"
API_KEY_UPDATE = "/api/keys/update"
API_KEY_DELETE = "/api/keys/delete"