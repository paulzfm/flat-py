# Copyright (c) 2014-present PlatformIO <contact@platformio.org>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# https://github.com/platformio/platformio-core/blob/591b377e4a4f7219b95531e447aec8d28fd41a79/platformio/account/validate.py#L48

import re

from flat.lib import select, xpath
from flat.py import lang, refine


class BadParameter(Exception):
    pass


def is_valid_username(value: str) -> bool:
    return all([c.isalpha() or c.isnumeric() or c == '-' for c in value]) and \
        not value.startswith('-') and not value.endswith('-') and \
        len(value) <= 38


def validate_username(value, field="username"):
    value = str(value).strip() if value else None
    if not value or not re.match(
            r"^[a-z\d](?:[a-z\d]|-(?=[a-z\d])){0,37}$", value, flags=re.I
    ):
        raise BadParameter(
            "Invalid %s format. "
            "%s must contain only alphanumeric characters "
            "or single hyphens, cannot begin or end with a hyphen, "
            "and must not be longer than 38 characters."
            % (field.lower(), field.capitalize())
        )
    return value


def validate_orgname(value):
    return validate_username(value, "Organization name")


def validate_email(value):
    value = str(value).strip() if value else None
    if not value or not re.match(
            r"^[a-z\d_\.\+\-]+@[a-z\d\-]+\.[a-z\d\-\.]+$", value, flags=re.I
    ):
        raise BadParameter("Invalid email address")
    return value


def is_valid_password(value: str) -> bool:
    return len(value) >= 8 and any([c.isdigit() for c in value]) and any([c.islower() for c in value])


def validate_password(value):
    value = str(value).strip() if value else None
    if not value or not re.match(r"^(?=.*[a-z])(?=.*\d).{8,}$", value):
        raise BadParameter(
            "Invalid password format. "
            "Password must contain at least 8 characters"
            " including a number and a lowercase letter"
        )
    return value


def is_valid_team_name(value: str) -> bool:
    return all([c.isalpha() or c.isnumeric() or c in {'-', '_', ' '} for c in value]) and \
        not value.startswith('-') and not value.startswith('_') and \
        not value.endswith('-') and not value.endswith('_') and \
        len(value) <= 20


def validate_teamname(value):
    value = str(value).strip() if value else None
    if not value or not re.match(
            r"^[a-z\d](?:[a-z\d]|[\-_ ](?=[a-z\d])){0,19}$", value, flags=re.I
    ):
        raise BadParameter(
            "Invalid team name format. "
            "Team name must only contain alphanumeric characters, "
            "single hyphens, underscores, spaces. It can not "
            "begin or end with a hyphen or a underscore and must"
            " not be longer than 20 characters."
        )
    return value


OrgTeamFormat = lang('OrgTeamFormat', """
start: org ":" team;
org: [0-9a-zA-Z_]+;
team: [0-9a-zA-Z_- ]+;
""")

OrgTeam = refine(OrgTeamFormat, lambda s: is_valid_username(select(xpath(OrgTeamFormat, '.org'), s)) and \
                                          is_valid_team_name(select(xpath(OrgTeamFormat, '.team'), s)))


def validate_orgname_teamname(value):
    value = str(value).strip() if value else None
    if not value or ":" not in value:
        raise BadParameter(
            "Please specify organization and team name using the following"
            " format - orgname:teamname. For example, mycompany:DreamTeam"
        )
    orgname, teamname = value.split(":", 1)
    validate_orgname(orgname)
    validate_teamname(teamname)
    return value
