#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Andy Sayler
# Summer 2014
# Univerity of Colorado

### Imports ###

import time
import os
import uuid
import multiprocessing
import functools
import sys

import flask
import flask.ext.httpauth
import flask.ext.cors

import redis

import cogs.config

import cogs.auth
import cogs.structs


### Constants ###

_FILES_KEY = "files"
_REPORTERS_KEY = "reporters"
_ASSIGNMENTS_KEY = "assignments"
_TESTS_KEY = "tests"
_SUBMISSIONS_KEY = "submissions"
_RUNS_KEY = "runs"
_TOKEN_KEY = "token"
_EXTRACT_KEY = "extract"

### Global Setup ###

app = flask.Flask(__name__)
cors = flask.ext.cors.CORS(app, headers=["Content-Type", "Authorization"])
httpauth = flask.ext.httpauth.HTTPBasicAuth()
srv = cogs.structs.Server()
auth = cogs.auth.Auth()
#workers = multiprocessing.Pool(10)
workers = None

### Logging ###

if cogs.config.LOGGING_ENABLED:

    import logging
    import logging.handlers

    loggers = [app.logger, logging.getLogger('cogs')]

    formatter_line = logging.Formatter('%(levelname)s: %(module)s - %(message)s')

    # Stream Handler
    handler_stream = logging.StreamHandler()
    handler_stream.setFormatter(formatter_line)
    handler_stream.setLevel(logging.WARNING)

    # File Handler
    if not os.path.exists(cogs.config.LOGGING_PATH):
        os.makedirs(cogs.config.LOGGING_PATH)
    logfile_path = "{:s}/{:s}".format(cogs.config.LOGGING_PATH, "api.log")
    handler_file = logging.handlers.WatchedFileHandler(logfile_path)
    handler_file.setFormatter(formatter_line)
    handler_file.setLevel(logging.INFO)

    for logger in loggers:
        logger.addHandler(handler_stream)
        logger.addHandler(handler_file)


### Functions ###

## Authentication Functions ##

@httpauth.verify_password
def verify_login(username, password):

    flask.g.user = None

    # Username:Password Case
    if password:
        user = auth.auth_userpass(username, password)
        if user:
            flask.g.user = user
            return True
        elif user == False:
            return False
        else:
            try:
                user = auth.create_user({}, username=username, password=password)
            except cogs.auth.BadCredentialsError:
                return False
            else:
                flask.g.user = user
                return True
    # Token Case
    else:
        user = auth.auth_token(username)
        if user:
            flask.g.user = user
            return True
        else:
            return False


def get_owner(func_get):

    def _decorator(func):

        @functools.wraps(func)
        def _wrapper(*args, **kwargs):

            # Get UUID
            obj_uuid = kwargs['obj_uuid']

            # Get Object
            obj = func_get(obj_uuid)

            # Get Owner
            flask.g.owner = obj.get('owner', None)

            # Call Function
            return func(*args, **kwargs)

        return _wrapper

    return _decorator

## Helper Functions ##

def error_response(e, status):

    err = { 'status': status,
            'message': str(e) }
    err_res = flask.jsonify(err)
    err_res.status_code = err['status']
    return err_res

def create_stub_json(func_create, **kwargs):

    data = flask.request.get_json(force=True)
    obj = func_create(data, owner=flask.g.user, **kwargs)
    obj_lst = list([str(obj.uuid)])
    return obj_lst

def create_stub_file(func_create, files=[]):

    obj_lst = []
    for file_obj in files:
        data = {}
        obj = func_create(data, file_obj=file_obj, owner=flask.g.user)
        obj_lst.append(str(obj.uuid))
    return obj_lst

def create_stub_files(func_create, files=[]):

    obj_lst = []
    for archive_obj in files:
        data = {}
        objs = func_create(data, archive_obj=archive_obj, owner=flask.g.user)
        for obj in objs:
            obj_lst.append(str(obj.uuid))
    return obj_lst

def update_stub_json(obj):

    data = flask.request.get_json(force=True)
    obj.set_dict(data)
    obj_dict = obj.get_dict()
    return obj_dict

def process_objects(func_list, func_create, key, create_stub=create_stub_json, raw=False, **kwargs):

    # List Objects
    if flask.request.method == 'GET':

        obj_lst = list(func_list())

    # Create Object
    elif flask.request.method == 'POST':
        obj_lst = create_stub(func_create, **kwargs)

    # Bad Method
    else:
        raise Exception("Unhandled Method")

    # Return Object List
    if raw:
        return obj_lst
    else:
        out = {key: obj_lst}
        return flask.jsonify(out)

def process_object(func_get, obj_uuid, update_stub=update_stub_json, raw=False):

    # Get Object
    obj = func_get(obj_uuid)

    # Get Object Data
    if flask.request.method == 'GET':
        obj_dict = obj.get_dict()

    # Update Object Data
    elif flask.request.method == 'PUT':
        obj_dict = update_stub(obj)

    # Delete Object
    elif flask.request.method == 'DELETE':
        obj_dict = obj.get_dict()
        obj.delete()

    # Bad Method
    else:
        raise Exception("Unhandled Method")

    # Return Object
    if raw:
        return obj_dict
    else:
        out = {str(obj.uuid): obj_dict}
        return flask.jsonify(out)

def process_uuid_list(func_list, func_add, func_remove, key):

    # Sanitize Input
    def sanitize_uuid_list(in_lst):
        out_lst = []
        for in_uuid in in_lst:
            out_uuid = str(uuid.UUID(in_uuid))
            out_lst.append(out_uuid)
        return out_lst

    # List Objects
    if flask.request.method == 'GET':

        out_lst = list(func_list())

    # Add Objects
    elif flask.request.method == 'PUT':
        in_obj = flask.request.get_json(force=True)
        in_lst = list(in_obj[key])
        add_lst = sanitize_uuid_list(in_lst)
        func_add(add_lst)
        out_lst = list(func_list())

    # Remove Objects
    elif flask.request.method == 'DELETE':
        in_obj = flask.request.get_json(force=True)
        in_lst = list(in_obj[key])
        rem_lst = sanitize_uuid_list(in_lst)
        func_remove(rem_lst)
        out_lst = list(func_list())

    # Bad Method
    else:
        raise Exception("Unhandled Method")

    # Return Object List

    out_obj = {key: out_lst}
    return flask.jsonify(out_obj)


### Endpoints ###

## Root Endpoints ##

@app.route("/", methods=['GET'])
def get_root():

    return app.send_static_file('index.html')

## Access Control Endpoints ##

@app.route("/tokens/", methods=['GET'])
@httpauth.login_required
@auth.requires_auth_route()
def get_token():

    # Get Token
    token = flask.g.user['token']

    # Return Token
    out = {str(_TOKEN_KEY): str(token)}
    return flask.jsonify(out)

# ToDo: User and Group Control

## File Endpoints ##

@app.route("/files/", methods=['GET'])
@httpauth.login_required
@auth.requires_auth_route()
def process_files_get():
    return process_objects(srv.list_files, None, _FILES_KEY, create_stub=None)

@app.route("/files/", methods=['POST'])
@httpauth.login_required
@auth.requires_auth_route()
def process_files_post():

    files = flask.request.files
    files_extract = []
    files_direct = []
    for key in files:
        if key == _EXTRACT_KEY:
            files_extract += files.getlist(key)
        else:
            files_direct += files.getlist(key)

    obj_lst = []
    if files_extract:
        obj_lst += process_objects(None, srv.create_files, _FILES_KEY,
                                   create_stub=create_stub_files, raw=True, files=files_extract)
    if files_direct:
        obj_lst += process_objects(None, srv.create_file, _FILES_KEY,
                                   create_stub=create_stub_file, raw=True, files=files_direct)

    out = {_FILES_KEY: obj_lst}
    return flask.jsonify(out)

@app.route("/files/<obj_uuid>/", methods=['GET', 'DELETE'])
@httpauth.login_required
@get_owner(srv.get_file)
@auth.requires_auth_route()
def process_file(obj_uuid):
    return process_object(srv.get_file, obj_uuid, update_stub=None)

## Reporter Endpoints ##

@app.route("/reporters/", methods=['GET', 'POST'])
@httpauth.login_required
@auth.requires_auth_route()
def process_reporters():
    return process_objects(srv.list_reporters, srv.create_reporter, _REPORTERS_KEY)

@app.route("/reporters/<obj_uuid>/", methods=['GET', 'PUT', 'DELETE'])
@httpauth.login_required
@get_owner(srv.get_reporter)
@auth.requires_auth_route()
def process_reporter(obj_uuid):
    return process_object(srv.get_reporter, obj_uuid)

## Assignment Endpoints ##

@app.route("/assignments/", methods=['GET', 'POST'])
@httpauth.login_required
@auth.requires_auth_route()
def process_assignments():
    return process_objects(srv.list_assignments, srv.create_assignment, _ASSIGNMENTS_KEY)

@app.route("/assignments/<obj_uuid>/", methods=['GET', 'PUT', 'DELETE'])
@httpauth.login_required
@get_owner(srv.get_assignment)
@auth.requires_auth_route()
def process_assignment(obj_uuid):
    return process_object(srv.get_assignment, obj_uuid)

@app.route("/assignments/<obj_uuid>/tests/", methods=['GET', 'POST'])
@httpauth.login_required
@get_owner(srv.get_assignment)
@auth.requires_auth_route()
def process_assignment_tests(obj_uuid):

    # Get Assignment
    asn = srv.get_assignment(obj_uuid)

    # Process Tests
    return process_objects(asn.list_tests, asn.create_test, _TESTS_KEY)

@app.route("/assignments/<obj_uuid>/submissions/", methods=['GET', 'POST'])
@httpauth.login_required
@get_owner(srv.get_assignment)
@auth.requires_auth_route()
def process_assignment_submissions(obj_uuid):

    # Get Assignment
    asn = srv.get_assignment(obj_uuid)

    # Process Submissions
    return process_objects(asn.list_submissions, asn.create_submission, _SUBMISSIONS_KEY)

## Test Endpoints ##

@app.route("/tests/", methods=['GET'])
@httpauth.login_required
@auth.requires_auth_route()
def process_tests():
    return process_objects(srv.list_tests, None, _TESTS_KEY)

@app.route("/tests/<obj_uuid>/", methods=['GET', 'PUT', 'DELETE'])
@httpauth.login_required
@get_owner(srv.get_test)
@auth.requires_auth_route()
def process_test(obj_uuid):
    return process_object(srv.get_test, obj_uuid)

@app.route("/tests/<obj_uuid>/files/", methods=['GET', 'PUT', 'DELETE'])
@httpauth.login_required
@get_owner(srv.get_test)
@auth.requires_auth_route()
def process_test_files(obj_uuid):

    # Get Test
    tst = srv.get_test(obj_uuid)

    # Process Files
    return process_uuid_list(tst.list_files, tst.add_files, tst.rem_files, _FILES_KEY)

@app.route("/tests/<obj_uuid>/reporters/", methods=['GET', 'PUT', 'DELETE'])
@httpauth.login_required
@get_owner(srv.get_test)
@auth.requires_auth_route()
def process_test_reporters(obj_uuid):

    # Get Test
    tst = srv.get_test(obj_uuid)

    # Process Reporters
    return process_uuid_list(tst.list_reporters, tst.add_reporters, tst.rem_reporters, _REPORTERS_KEY)

## Submission Endpoints ##

@app.route("/submissions/", methods=['GET'])
@httpauth.login_required
@auth.requires_auth_route()
def process_submissions():
    return process_objects(srv.list_submissions, None, _SUBMISSIONS_KEY)

@app.route("/submissions/<obj_uuid>/", methods=['GET', 'PUT', 'DELETE'])
@httpauth.login_required
@get_owner(srv.get_submission)
@auth.requires_auth_route()
def process_submission(obj_uuid):
    return process_object(srv.get_submission, obj_uuid)

@app.route("/submissions/<obj_uuid>/files/", methods=['GET', 'PUT', 'DELETE'])
@httpauth.login_required
@get_owner(srv.get_submission)
@auth.requires_auth_route()
def process_submission_files(obj_uuid):

    # Get Submission
    sub = srv.get_submission(obj_uuid)

    # Process Files
    return process_uuid_list(sub.list_files, sub.add_files, sub.rem_files, _FILES_KEY)

@app.route("/submissions/<obj_uuid>/runs/", methods=['GET', 'POST'])
@httpauth.login_required
@get_owner(srv.get_submission)
@auth.requires_auth_route()
def process_submission_runs(obj_uuid):

    # Get Submission
    sub = srv.get_submission(obj_uuid)

    # Process Runs
    return process_objects(sub.list_runs, sub.execute_run, _RUNS_KEY, workers=workers)

## Run Endpoints ##

@app.route("/runs/", methods=['GET'])
@httpauth.login_required
@auth.requires_auth_route()
def process_runs():
    return process_objects(srv.list_runs, None, _RUNS_KEY)

@app.route("/runs/<obj_uuid>/", methods=['GET', 'DELETE'])
@httpauth.login_required
@get_owner(srv.get_run)
@auth.requires_auth_route()
def process_run(obj_uuid):
    return process_object(srv.get_run, obj_uuid)


### Exceptions ###

@app.errorhandler(cogs.auth.UserNotAuthorizedError)
def not_authorized(error):
    err = { 'status': 401,
            'message': str(error) }
    res = flask.jsonify(err)
    res.status_code = err['status']
    return res

@app.errorhandler(cogs.structs.ObjectDNE)
def not_found(error=False):
    err = { 'status': 404,
            'message': "Not Found: {:s}".format(flask.request.url) }
    res = flask.jsonify(err)
    res.status_code = err['status']
    return res

@app.errorhandler(KeyError)
def bad_key(error):
    err = { 'status': 400,
            'message': "{:s}".format(error) }
    res = flask.jsonify(err)
    res.status_code = err['status']
    return res

@app.errorhandler(ValueError)
def bad_key(error):
    err = { 'status': 400,
            'message': "{:s}".format(error) }
    res = flask.jsonify(err)
    res.status_code = err['status']
    return res

@app.errorhandler(TypeError)
def bad_key(error):
    err = { 'status': 400,
            'message': "{:s}".format(error) }
    res = flask.jsonify(err)
    res.status_code = err['status']
    return res

@app.errorhandler(400)
def bad_request(error=False):
    err = { 'status': 400,
            'message': "Malformed request" }
    res = flask.jsonify(err)
    res.status_code = err['status']
    return res

@app.errorhandler(404)
def not_found(error=False):
    err = { 'status': 404,
            'message': "Not Found: {:s}".format(flask.request.url) }
    res = flask.jsonify(err)
    res.status_code = err['status']
    return res

@app.errorhandler(405)
def bad_method(error=False):
    err = { 'status': 405,
            'message': "Bad Method: {:s} {:s}".format(flask.request.method, flask.request.url) }
    res = flask.jsonify(err)
    res.status_code = err['status']
    return res

### Run Test Server ###

if __name__ == "__main__":
    app.run(debug=True)
