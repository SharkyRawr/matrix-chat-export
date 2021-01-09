import json
import os
import re
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin

import requests

PUT_ROOM_STATE_API = r'/_matrix/client/r0/rooms/{roomid}/state/m.room.member/{userid}'
GET_PRESENCE_STATUS_API = r'/_matrix/client/r0/presence/{userid}/status'
GET_JOINED_ROOMS_API = r'/_matrix/client/r0/joined_rooms'
GET_ROOM_NAME_API = r'/_matrix/client/r0/rooms/{roomid}/state/m.room.name/'
GET_ROOM_MEMBERS_API = r'/_matrix/client/r0/rooms/{roomid}/joined_members'
POST_MEDIA_UPLOAD_API = r'/_matrix/media/r0/upload'
GET_USER_PROFILE_API = r'/_matrix/client/r0/profile/{userid}'
PUT_ROOM_TAGS = r'/_matrix/client/r0/user/{userid}/rooms/{roomid}/tags/{tag}'
GETPUT_ACCOUNT_DATA = r'/_matrix/client/r0/user/{userid}/account_data/{type}'
GET_WHOAMI = r'/_matrix/client/r0/account/whoami'

# Media requests
GET_MEDIA_THUMBNAIL = r'/_matrix/media/r0/thumbnail/{servername}/{mediaid}'

MXC_RE = re.compile(r'^mxc://(.+)/(.+)')


class MatrixUserProfile(object):
    avatar_url: str
    displayname: str

    def __init__(self, from_dict: Optional[dict] = None) -> None:
        if from_dict:
            for k in from_dict.keys():
                setattr(self, k, from_dict[k])

    @property
    def name(self) -> str:
        if hasattr(self, 'display_name'):
            return getattr(self, 'display_name')
        else:
            return self.displayname


class MatrixRoom(object):
    matrix = None

    def __init__(self, room_id: str, name: str = None) -> None:
        self.room_id = room_id
        self.name = name

    def __str__(self) -> str:
        if self.name:
            return self.name
        return self.room_id

    def has_name(self) -> bool:
        return self.name != None

    def set_name(self, name: str) -> None:
        self.name = name


class MatrixAPI(object):
    def __init__(self,  access_token: str = None,
                 homeserver: str = "https://matrix-client.matrix.org",
                 user_id: str = None,
                 ):
        self.access_token = access_token
        if self.access_token:
            self.access_token = self.access_token.strip()

        self.homeserver = homeserver
        if self.homeserver:
            self.homeserver = self.homeserver.strip()

        self.user_id = user_id
        if self.user_id:
            self.user_id = self.user_id.strip()

    def set_token(self, access_token: str) -> None:
        self.access_token = access_token

    def do(self, method: str, url: str, json: dict = None, headers: Dict[str, str] = None, **kwargs):
        hdr = {
            'Authorization': r'Bearer {}'.format(self.access_token)
        }
        if headers is not None:
            hdr.update(headers)

        _rm = getattr(requests, method)
        r = _rm(urljoin(self.homeserver, url),
                json=json, headers=hdr, **kwargs)
        return r

    def save(self, statefile='settings.json') -> None:
        with open(statefile, 'w') as f:
            json.dump(dict(
                access_token=self.access_token,
                homeserver=self.homeserver,
                user_id=self.user_id
            ), f)

    def load(self, statefile='settings.json') -> bool:
        try:
            with open(statefile) as f:
                data: dict = json.load(f)
                for k in set(['access_token', 'homeserver', 'user_id']):
                    if k in data:
                        setattr(self, k, data[k])
            return True

        except FileNotFoundError:
            return False
        except Exception as ex:
            raise

    def get_presence(self, userid: str = None) -> Any:
        uid = userid or self.user_id

        r = self.do('get', GET_PRESENCE_STATUS_API.format(userid=uid))
        r.raise_for_status()
        return r.json()

    def update_roomstate(self, room: Union[MatrixRoom, str], displayname: str = None, avatarmxc: str = None):
        args = {
            'membership': 'join'
        }
        if displayname:
            args['displayname'] = displayname
        if avatarmxc:
            args['avatar_url'] = avatarmxc

        if not displayname and not avatarmxc:
            raise AssertionError(
                "What exactly are you trying to do? Set a room-nick or room-avatar and try again.")

        room = room.room_id if type(room) is MatrixRoom else room

        r = self.do('put', PUT_ROOM_STATE_API.format(
            roomid=room, userid=self.user_id), json=args)
        r.raise_for_status()
        return r.json()

    def get_rooms(self) -> List[str]:
        r = self.do('get', GET_JOINED_ROOMS_API)
        r.raise_for_status()
        return r.json()['joined_rooms']

    def get_room_name(self, room: Union[MatrixRoom, str]) -> Optional[str]:
        r = self.do('get', GET_ROOM_NAME_API.format(
            roomid=room.room_id if type(room) is MatrixRoom else room))

        r.raise_for_status()

        data: dict = r.json()
        return data.get('name', None)

    def get_room_members(self, room: Union[MatrixRoom, str], exclude_myself: bool = False) -> List[MatrixUserProfile]:
        r = self.do('get', GET_ROOM_MEMBERS_API.format(
            roomid=room.room_id if type(room) is MatrixRoom else room))
        r.raise_for_status()

        data: dict = r.json()
        joined_members: list = data['joined']
        if exclude_myself:
            members = []
            for uid in joined_members:
                if exclude_myself and uid == self.user_id:
                    continue
                members.append(MatrixUserProfile(joined_members[uid]))
            return members
        return [MatrixUserProfile(joined_members[uid]) for uid in joined_members]

    def upload_media(self, filename: str, content_type: str = None) -> str:
        from mimetypes import guess_type
        guessed_type, _ = guess_type(filename)
        ct = content_type or str(guessed_type)
        with open(filename, 'rb') as f:
            r = self.do('post', POST_MEDIA_UPLOAD_API, headers={
                        'content-type': ct}, params=dict(filename=os.path.basename(filename)), data=f)
        r.raise_for_status()
        return r.json()['content_uri']

    def get_user_profile(self, user_id: Optional[str]) -> MatrixUserProfile:
        r = self.do('get', GET_USER_PROFILE_API.format(
            userid=user_id or self.user_id))
        r.raise_for_status()

        data: dict = r.json()
        m = MatrixUserProfile(data)
        return m

    def put_room_tag(self, room: Union[MatrixRoom, str], tag: str):
        room_id: str
        if type(room) is MatrixRoom:
            room_id = room.room_id
        else:
            room_id = room

        r = self.do("put", PUT_ROOM_TAGS.format(
                roomid=room_id, userid=self.user_id, tag="u." + tag
            ), json={}
        )
        r.raise_for_status()

    def get_account_data(self, userid: str, type: str) -> dict:
        r = self.do('get', GETPUT_ACCOUNT_DATA.format(
            userid=userid, type=type
        ))
        r.raise_for_status()
        return r.json()

    def put_account_data(self, userid: str, type: str, data: Dict) -> dict:
        r = self.do('put', GETPUT_ACCOUNT_DATA.format(
            userid=userid, type=type
        ), json=data)
        r.raise_for_status()
        return r.json()

    def media_get_thumbnail(self, mxcurl: str, width: int, height: int) -> bytes:

        m = MXC_RE.search(mxcurl)
        if m is None:
            raise Exception("MXC url could not be parsed")
        if len(m.groups()) == 2:
            servername, mediaid = m.groups()

            r = self.do('get', GET_MEDIA_THUMBNAIL.format(
                servername=servername, mediaid=mediaid
            ), params=dict(width=width, height=height))
            r.raise_for_status()
            content: bytes = r.content
            return content

        raise Exception("media download failed or some regexp shit i dunno")

    def whoami(self):
        r = self.do('get', GET_WHOAMI)
        r.raise_for_status()
        return r.json()
