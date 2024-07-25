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

from flat.py import lang, refine, fuzz


class BadParameter(Exception):
    pass


UsernameFormat = lang('UsernameFormat', """
start: char{1,38};
char: [a-zA-Z0-9-];
""")

Username = refine(UsernameFormat, "not _.startswith('-') and not _.endswith('-')")


def validate_username(value: Username, field="username"):
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


PasswordFormat = lang('PasswordFormat', """
start: char{8,};
char: [0-9A-Za-z-];
""")


def is_valid_password(value: str) -> bool:
    return any([c.isdigit() for c in value]) and any([c.islower() for c in value])


Password = refine(PasswordFormat, 'is_valid_password(_)')


def validate_password(value: Password):
    ...

    value = str(value).strip() if value else None
    if not value or not re.match(r"^(?=.*[a-z])(?=.*\d).{8,}$", value):
        raise BadParameter(
            "Invalid password format. "
            "Password must contain at least 8 characters"
            " including a number and a lowercase letter"
        )
    return value


TeamNameFormat = lang('TeamNameFormat', """
start: char{1,20};
char: [a-zA-Z0-9-_ ];
""")

TeamName = refine(TeamNameFormat, "not _.startswith('-') and not _.endswith('-') and not _.startswith('_') "
                                  "and not _.endswith('_')")


def validate_teamname(value: TeamName):
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


def main():
    fuzz(validate_username, 1000)
    fuzz(validate_password, 1000)
    fuzz(validate_teamname, 1000)
