# -*- coding: utf-8 -*-

# Copyright 2018 University of Maryland Balloon Payload Program
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Provide the HTTP API for aprsistrack.
"""

from flask import Flask, jsonify, request, g
import mysql.connector
from datetime import datetime
import requests
from time import strftime, gmtime
from aprsistrack.secrets import (SECRET_MYSQL_DATABASE_USER,
                                 SECRET_MYSQL_DATABASE_PASSWORD,
                                 SECRET_MYSQL_DATABASE_DB,
                                 SECRET_SECRET_APRS_FI_API_KEY)
app = Flask(__name__)

# MySQL configurations
app.config['MYSQL_DATABASE_USER'] = SECRET_MYSQL_DATABASE_USER
app.config['MYSQL_DATABASE_PASSWORD'] = SECRET_MYSQL_DATABASE_PASSWORD
app.config['MYSQL_DATABASE_DB'] = SECRET_MYSQL_DATABASE_DB
app.config['APRS_FI_API_KEY'] = SECRET_SECRET_APRS_FI_API_KEY
app.config['MYSQL_DATABASE_HOST'] = 'localhost'
app.config['TRACKED_CALLSIGNS_TABLE'] = 'tracked_callsigns'
app.config['PACKETS_TABLE'] = 'packets'

# TODO pooling
cnx = mysql.connector.connect(user=app.config['MYSQL_DATABASE_USER'],
                              password=app.config['MYSQL_DATABASE_PASSWORD'],
                              host=app.config['MYSQL_DATABASE_HOST'],
                              database=app.config['MYSQL_DATABASE_DB'])

cursor = cnx.cursor() # TODO appropriate? Or should each method get a new cursor


API_VERSION = '0.1'  # TODO roll on release


# TODO write some exceptions


def validate_callsign(callsign: str):
    # TODO
    pass

def _get_tracked_callsigns():  # TODO type hint
    query = 'SELECT callsign FROM ' + app.config['MYSQL_DATABASE_DB'] +\
            '.' + app.config['TRACKED_CALLSIGNS_TABLE'] + ';'
    cursor.execute(query)
    return [result[0] for result in cursor.fetchall()]

def _update_aprsis_filter() -> None:
    tracked_callsigns = _get_tracked_callsigns()
    if len(tracked_callsigns) == 0:
        filter_string = 'default'
    else:
        filter_string = '/'.join(['p'] + tracked_callsigns)
    # TODO convert to byte string?
    # TODO notify listener process of new filter
    print(filter_string)  # TODO debugging - change to log statement

def _add_callsign(callsign: str, track_permanently: bool = False) -> None:
    query  = 'INSERT INTO ' +  app.config['MYSQL_DATABASE_DB'] +\
            '.' + app.config['TRACKED_CALLSIGNS_TABLE'] + \
            ' VALUES (%s, %s, %s);'
    cursor.execute(query, (callsign, int(track_permanently),
                   str(datetime.now())))  # TODO UTC-ify
    cnx.commit()
    _update_aprsis_filter()

    aprs_fi_url_template = "https://api.aprs.fi/api/get?name={0}&what=loc&apikey={1}&format=json"
    aprs_fi_data = requests.get(aprs_fi_url_template.format(callsign, app.config['APRS_FI_API_KEY']))
    aprs_fi_json = aprs_fi_data.json()
    if aprs_fi_json["result"] != "ok":
        # TODO raise exception
        pass
    aprs_fi_last_position_json = aprs_fi_json['entries'][0]
    aprs_fi_callsign = aprs_fi_last_position_json["name"]
    if aprs_fi_callsign != callsign:
        # TODO raise exception
        pass
    aprs_fi_timestamp = int(aprs_fi_last_position_json["time"])  # TODO parse from linux time
    aprs_fi_datetime = strftime('%Y-%m-%d %H:%M:%S', gmtime(aprs_fi_timestamp))  # TODO gmtime or localtime?
    aprs_fi_lat = aprs_fi_last_position_json["lat"]
    aprs_fi_lng = aprs_fi_last_position_json["lng"]
    aprs_fi_alt = aprs_fi_last_position_json["altitude"]
    aprs_fi_comment = aprs_fi_last_position_json["comment"]
    aprs_fi_path = aprs_fi_last_position_json["path"]

    query = 'INSERT INTO ' + app.config['MYSQL_DATABASE_DB'] + '.' + \
            app.config['PACKETS_TABLE'] + ' ' + \
            '(callsign, timestamp, lat, lng, alt, comment, path) ' + \
            ' VALUES (%s, %s, %s, %s, %s, %s, %s);'

    cursor.execute(query, (aprs_fi_callsign, aprs_fi_datetime, aprs_fi_lat, aprs_fi_lng, aprs_fi_alt,
                           aprs_fi_comment, aprs_fi_path))
    cnx.commit()

def _remove_callsign(callsign: str) -> None:
    query  = 'DELETE FROM ' +  app.config['MYSQL_DATABASE_DB'] +\
            '.' + app.config['TRACKED_CALLSIGNS_TABLE'] + \
            ' WHERE callsign = %s;'
    cursor.execute(query, (callsign,))
    cnx.commit()
    _update_aprsis_filter()


def query_database_for_callsign(callsign: str, results_per_callsign: int) -> str: # TODO return type
    query = 'SELECT * FROM ' +  app.config['MYSQL_DATABASE_DB'] +\
            '.' + app.config['PACKETS_TABLE'] + \
            ' WHERE callsign = %s ORDER BY datetime_added DESC LIMIT %s;'
    cursor.execute(query, (callsign, results_per_callsign))
    return cursor.fetchall()

# Flask App ###################################################################
@app.route('/api/v{0}/'.format(API_VERSION), methods=['GET'])
def handle_get():
    """
    Single API endpoint which accepts GET requests.
    """
    callsign_string = str(request.args['callsigns']).upper()
    entries_per_callsign = int(request.args['entries_per_callsign'])
    requested_callsigns : list[str] = callsign_string.split(',')
    # TODO create response in JSON format
    response = {''}
    for callsign in requested_callsigns:
        validate_callsign(callsign)
        if callsign in _get_tracked_callsigns():
            response[callsign] = query_database_for_callsign(callsign, entries_per_callsign)
        else:
            _add_callsign(callsign)
            response[callsign] = query_database_for_callsign(callsign, entries_per_callsign)
    response['metadata'] = None # TODO
    return jsonify(response)

@app.errorhandler(Exception)
def handle_exception(error):
    pass # TODO

