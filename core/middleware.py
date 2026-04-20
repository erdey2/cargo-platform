from urllib.parse import parse_qs
from channels.middleware import BaseMiddleware
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async
from apps.users.models import User


@database_sync_to_async
def get_user(token):
    try:
        access_token = AccessToken(token)
        user = User.objects.get(id=access_token["user_id"])
        return user
    except Exception:
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):

    async def __call__(self, scope, receive, send):
        query_string = scope["query_string"].decode()
        print("QUERY STRING:", query_string)

        params = parse_qs(query_string)
        token = params.get("token")
        print("TOKEN:", token)

        if token:
            scope["user"] = await get_user(token[0])
        else:
            scope["user"] = AnonymousUser()

        print("USER:", scope["user"])
        return await super().__call__(scope, receive, send)