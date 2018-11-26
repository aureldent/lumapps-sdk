from __future__ import print_function, unicode_literals
import json
import os
import sys
import logging
from datetime import datetime, timedelta
from textwrap import TextWrapper

from google.oauth2 import service_account
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

GOOGLE_APIS = ("drive", "admin", "groupssettings")
TOKEN_VALIDITY_DURATION = 60 * 60


def get_conf_file():
    if "APPDATA" in os.environ:
        d = os.environ["APPDATA"]
    elif "XDG_CONFIG_HOME" in os.environ:
        d = os.environ["XDG_CONFIG_HOME"]
    else:
        d = os.path.join(os.path.expanduser("~"), ".config")
    if __package__:
        return os.path.join(d, __package__ + ".conf")
    else:
        return os.path.join(d, "lumapps_api_client.conf")


def get_conf():
    try:
        with open(get_conf_file()) as fh:
            conf = json.load(fh)
    except IOError:
        return {"configs": {}, "cache": {}}
    if not conf:
        conf = {"configs": {}, "cache": {}}
    # ###### to remove soon enough ######
    if "configs" not in conf and conf:
        conf = {"configs": conf, "cache": {}}
        set_conf(conf)
    # ###################################
    return conf


def set_conf(conf):
    try:
        with open(get_conf_file(), "wt") as fh:
            return json.dump(conf, fh, indent=4)
    except IOError as e:
        print("failed to save conf: {}".format(e), file=sys.stderr)


class ApiCallError(Exception):
    pass


class DiscoveryCache(object):
    _max_age = 60 * 60 * 24  # 1 day

    @staticmethod
    def get(url):
        cached = get_conf()["cache"].get(url)
        if not cached:
            return None
        expiry_dt = datetime.strptime(cached["expiry"][:19], "%Y-%m-%dT%H:%M:%S")
        if expiry_dt < datetime.now():
            return None
        return cached["content"]

    @staticmethod
    def set(url, content):
        conf = get_conf()
        conf["cache"][url] = {
            "expiry": (
                datetime.now() + timedelta(seconds=DiscoveryCache._max_age)
            ).isoformat()[:19],
            "content": content,
        }
        set_conf(conf)


class ApiClient(object):
    def __init__(
        self,
        auth_info=None,
        api_info=None,
        credentials=None,
        user=None,
        token=None,
        enable_cache=False,
            base_url="https://lumsites.appspot.com"
    ):
        self._auth_info = auth_info
        self._user = {}
        self.email = ""
        self.last_cursor = None
        self.cache = None
        self.token_expiration = None
        self.customerId = None
        self.instanceId = None

        if not api_info:
            api_info = {}
        self.api_info = api_info
        self._api_name = api_info.get("name", "lumsites")
        self._api_scopes = api_info.get(
            "scopes", ["https://www.googleapis.com/auth/userinfo.email"]
        )
        self._api_version = api_info.get("version", "v1")
        self.base_url = api_info.get("base_url", base_url).rstrip(
            "/"
        )
        if credentials:
            self.creds = credentials
        elif auth_info and "refresh_token" in auth_info:
            self.creds = Credentials(None, **auth_info)
        elif auth_info and "bearer" in auth_info:
            self.creds = Credentials(auth_info["bearer"].replace("Bearer ", ""))
        elif token:
            self.creds = Credentials(token)
        elif auth_info:  # service account
            self.creds = service_account.Credentials.from_service_account_info(
                auth_info
            )
            if self._api_scopes:
                self.creds = self.creds.with_scopes(self._api_scopes)
            if user:
                self.creds = self.creds.with_subject(user)
        else:
            self.creds = Credentials(None)
        if self._api_name in GOOGLE_APIS:
            url_path = "discovery/v1/apis"
        else:
            url_path = "_ah/api/discovery/v1/apis"
        self._url = "{}/{}/{}/{}/rest".format(
            self.base_url, url_path, self._api_name, self._api_version
        )
        self._methods = None
        self._service = None

        if user:
            self.email = user
        # self._service_timestamp = None

        if enable_cache:
            self.cache = DiscoveryCache()

    def get_new_client_as(self, user):
        return ApiClient(self._auth_info, self.api_info, user=user)

    @property
    def token(self):
        if not self.creds.token:
            self.service._http.request(self.base_url)
        return self.creds.token

    @token.setter
    def token(self, v):
        if self.creds.token == v:
            return
        self.creds.token = v
        if self._service:
            self._service._http.credentials.token = v

    @property
    def service(self):

        # if there is an expiration deadline reset the service

        if self.token_expiration:
            expiry_dt = datetime.strptime(self.token_expiration, "%Y-%m-%dT%H:%M:%S")
            # if expiry_dt < datetime.now():
            remaining_time = expiry_dt - datetime.now()
            logging.info(
                "remaining time %s %s %s",
                self.token_expiration,
                expiry_dt,
                remaining_time,
            )

            if remaining_time.total_seconds() <= 30:
                logging.info(
                    "token expired, resetting the token %s", self.token_expiration
                )
                email = self.email
                customerId = self.customerId
                ApiClient.__init__(self, auth_info=self._auth_info)
                self.set_customer_user(email, customerId)

        if self._service is None:
            self._service = build(
                self._api_name,
                self._api_version,
                discoveryServiceUrl=self._url,
                credentials=self.creds,
                cache_discovery=True,
                cache=self.cache,
            )
        return self._service

    @property
    def methods(self):
        if self._methods is None:
            self._methods = {
                n: m for n, m in self.walk_api_methods(self.service._resourceDesc)
            }
        return self._methods

    def get_help(self, method_parts, debug=False):
        help_lines = []

        def w(l):
            help_lines.append(l)

        wrapper = TextWrapper(initial_indent="\t", subsequent_indent="\t")
        method = self.methods[method_parts]
        w(method.get("httpMethod", "?") + " method: " + " ".join(method_parts) + "\n")
        if "description" in method:
            w(method["description"].strip() + "\n")
        if debug:
            w(json.dumps(method, indent=4, sort_keys=True))
        params = method.get("parameters", {})
        if method.get("httpMethod", "") == "POST":
            params.update(
                {"body": {"required": True, "type": "JSON"}, "fields": {"type": "JSON"}}
            )
        if not params:
            w("API method takes no parameters")
        else:
            w("Parameters (*required):")
            for param_name in sorted(params):
                param = params[param_name]
                descr = param.get("description")
                descr = "\n" + wrapper.fill(descr) if descr else ""
                w(
                    "  {}: {} {} {}".format(
                        param_name,
                        param["type"],
                        "*" if param.get("required") else "",
                        descr,
                    )
                )
        return "\n".join(help_lines)

    def get_method_descriptions(self, methods):
        lines = []
        for method_parts in methods:
            method = self.methods[method_parts]
            lines.append(
                (
                    " ".join(method_parts),
                    method.get("description", "").strip().split("\n")[0],
                )
            )
        longest_name = max(len(l[0]) for l in lines)
        fmt = "  {{: <{}}}  {{}}".format(longest_name)
        return "\n".join(fmt.format(*l) for l in lines)

    def walk_api_methods(self, resource, parents=()):
        for method_name, method in resource.get("methods", {}).items():
            yield tuple(parents + (method_name,)), method
        for rsc_name, rsc in resource.get("resources", {}).items():
            for method_name, method in self.walk_api_methods(
                rsc, tuple(parents + (rsc_name,))
            ):
                yield method_name, method

    def get_api_call(self, method_parts, params):
        api_call = self.service

        for part in method_parts[:-1]:
            api_call = getattr(api_call, part)()
        try:
            return getattr(api_call, method_parts[-1])(**params)
        except TypeError as err:
            raise ApiCallError(err)

    def get_call(self, *method_parts, **params):
        if params is None:
            params = {}
        items = []
        cursor = None
        if "body" in params and isinstance(params["body"], str):
            params["body"] = json.loads(params["body"])
        while True:
            if cursor:
                if "body" in params:
                    params["body"]["cursor"] = cursor
                else:
                    params["cursor"] = cursor
            response = self.get_api_call(method_parts, params).execute(num_retries=5)

            if "more" in response and "items" not in response:
                self.last_cursor = None
                return items  # empty list
            if "more" in response and "items" in response:
                items.extend(response["items"])
                if response.get("more", False):
                    self.last_cursor = cursor = response["cursor"]
                else:
                    return items
            else:
                self.last_cursor = None
                return response

    def iter_call(self, *method_parts, **params):
        if params is None:
            params = {}
        cursor = None

        if "body" in params and isinstance(params["body"], str):
            params["body"] = json.loads(params["body"])
        while True:
            if cursor:

                if "body" in params:
                    params["body"]["cursor"] = cursor
                else:
                    params["cursor"] = cursor

            response = self.get_api_call(method_parts, params).execute(num_retries=5)

            if "more" in response and "items" not in response:
                self.last_cursor = None
                return  # empty list
            if "more" in response and "items" in response:
                if response.get("more", False):
                    cursor = response["cursor"]
                    self.last_cursor = cursor

                for item in response["items"]:
                    yield item
                else:
                    return
            else:
                yield response

    def get_matching_methods(self, method_parts):
        # find exact matches of all parts up to but excluding last
        matches = [n for n in self.methods if len(n) >= len(method_parts)]
        for i, part in enumerate(method_parts[:-1]):
            matches = [n for n in matches if len(n) >= i and n[i] == part]
        # find 'startswith' matches of the last part
        last = method_parts[-1]
        idx = len(method_parts) - 1
        matches = [m for m in matches if len(m) >= idx and m[idx].startswith(last)]
        if not matches:
            return "API method not found"
        return (
            "API method not found. Did you mean any of these?\n"
            + self.get_method_descriptions(sorted(matches))
        )

    def set_customer_user(self, email, customerId, instanceId=None):
        token = self.get_call("user", "getToken", email=email, customerId=customerId)
        self._user = {}
        if token and token.get("accessToken"):
            self.token_expiration = (
                datetime.now() + timedelta(seconds=TOKEN_VALIDITY_DURATION)
            ).isoformat()[:19]
            self.token = token.get("accessToken")
            self.email = email
            self.customerId = customerId
            self.instanceId = instanceId

            logging.info("getting customer token %s %s", token, self.token_expiration)

        else:
            raise Exception("USER_NOT_ALLOWED_FOR_CUSTOMER")

    @property
    def user(self):
        if not self._user:
            if not self.email:
                raise Exception()
            self._user = self.get_call("user", "get", email=self.email)
        return self._user

    @property
    def customer(self):
        return self.user.get("customer", None)

    def is_admin_instance(self, instance):
        if self.is_admin_platform():
            return True
        instances_admin = self.user.get("instancesSuperAdmin", None)
        return not instances_admin or instance in instances_admin

    def is_admin_platform(self):
        if self.is_god():
            return True

        is_super_admin = self.user.get("isSuperAdmin", False)
        return bool(is_super_admin)

    def is_god(self):
        return bool(self.user.get("isGod", False))
