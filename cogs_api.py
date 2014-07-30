#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Andy Sayler
# Summer 2014
# Univerity of Colorado

import flask

import cogs.datatypes as datatypes

app = flask.Flask(__name__)

_MSG_ROOT = "Welcome to the CU CS Online Grading System API"

_ASSIGNMENTS_KEY = "assignments"
_TESTS_KEY = "tests"

### Endpoints

## Root Endpoints

@app.route("/", methods=['GET'])
def get_root():
    res = _MSG_ROOT
    return res

## Assignment Endpoints

@app.route("/assignments/", methods=['GET', 'POST'])
def process_assignments():

    # Create Server
    srv = datatypes.Server()

    if flask.request.method == 'GET':
        # Get Assignments
        out = {_ASSIGNMENTS_KEY: list(srv.list_assignments())}
    elif flask.request.method == 'POST':
        # Create Assignment
        d = flask.request.get_json(force=True)
        try:
            asn = srv.create_assignment(d)
        except KeyError as e:
            err = {
                'status': 400,
                'message': str(e)
            }
            err_res = flask.jsonify(err)
            err_res.status_code = err['status']
            return err_res
        else:
            out = {_ASSIGNMENTS_KEY: list([repr(asn)])}
    else:
        raise Exception("Unhandled Method")

    # Return Assignment List
    res = flask.jsonify(out)
    return res

@app.route("/assignments/<uuid_hex>/", methods=['GET', 'PUT', 'DELETE'])
def process_assignment(uuid_hex):

    # Create Server
    s = datatypes.Server()

    # Get Assignment
    try:
        a = s.get_assignment(uuid_hex)
    except datatypes.UUIDRedisObjectDNE as e:
        err = {
            'status': 404,
            'message': str(e)
        }
        err_res = flask.jsonify(err)
        err_res.status_code = err['status']
        return err_res

    if flask.request.method == 'GET':
        # Get Assignment
        out = {repr(a): a.get_dict()}
    elif flask.request.method == 'PUT':
        # Update Assignment
        d = flask.request.get_json(force=True)
        try:
            a.set_dict(d)
        except KeyError as e:
            err = {
                'status': 400,
                'message': str(e)
            }
            err_res = flask.jsonify(err)
            err_res.status_code = err['status']
            return err_res
        else:
            out = {repr(a): a.get_dict()}
    elif flask.request.method == 'DELETE':
        # Delete Assignment
        out = {repr(a): a.get_dict()}
        a.delete()
    else:
        raise Exception("Unhandled Method")

    # Return Assignment
    res = flask.jsonify(out)
    return res


## Assignment Test Endpoints

@app.route("/assignments/<asn_uuid>/tests/", methods=['GET', 'POST'])
def process_tests(asn_uuid):

    # Create Server
    srv = datatypes.Server()

    # Get Assignment
    try:
        asn = srv.get_assignment(asn_uuid)
    except datatypes.UUIDRedisObjectDNE as e:
        err = {
            'status': 404,
            'message': str(e)
        }
        err_res = flask.jsonify(err)
        err_res.status_code = err['status']
        return err_res

    if flask.request.method == 'GET':
        # Get Tests
        out = {_TESTS_KEY: list(asn.list_tests())}
    elif flask.request.method == 'POST':
        # Create Test
        d = flask.request.get_json(force=True)
        try:
            tst = asn.create_test(d)
        except KeyError as e:
            err = {
                'status': 400,
                'message': str(e)
            }
            err_res = flask.jsonify(err)
            err_res.status_code = err['status']
            return err_res
        else:
            out = {_TESTS_KEY: list([repr(tst)])}
    else:
        raise Exception("Unhandled Method")

    # Return Test List
    res = flask.jsonify(out)
    return res

@app.route("/assignments/<asn_uuid>/tests/<tst_uuid>/", methods=['GET', 'PUT', 'DELETE'])
def process_test(asn_uuid, tst_uuid):

    # Create Server
    srv = datatypes.Server()

    # Get Assignment
    try:
        asn = srv.get_assignment(asn_uuid)
    except datatypes.UUIDRedisObjectDNE as e:
        err = {
            'status': 404,
            'message': str(e)
        }
        err_res = flask.jsonify(err)
        err_res.status_code = err['status']
        return err_res

    # Get Test
    try:
        tst = asn.get_test(tst_uuid)
    except datatypes.UUIDRedisObjectDNE as e:
        err = {
            'status': 404,
            'message': str(e)
        }
        err_res = flask.jsonify(err)
        err_res.status_code = err['status']
        return err_res

    if flask.request.method == 'GET':
        # Get Assignment
        out = {repr(tst): tst.get_dict()}
    elif flask.request.method == 'PUT':
        # Update Assignment
        d = flask.request.get_json(force=True)
        try:
            tst.set_dict(d)
        except KeyError as e:
            err = {
                'status': 400,
                'message': str(e)
            }
            err_res = flask.jsonify(err)
            err_res.status_code = err['status']
            return err_res
        else:
            out = {repr(tst): tst.get_dict()}
    elif flask.request.method == 'DELETE':
        # Delete Assignment
        out = {repr(tst): tst.get_dict()}
        tst.delete()
    else:
        raise Exception("Unhandled Method")

    # Return Test
    res = flask.jsonify(out)
    return res


## Other Endpoints

@app.route("/test/", methods=['POST'])
def test_upload():
    print("Testing upload...")
    print("files = {:s}".format(flask.request.files))
    return flask.jsonify({"status": "done"})


### Exceptions

@app.errorhandler(400)
def bad_request(error=False):
    message = {
            'status': 400,
            'message': "Malformed request"
    }
    res = flask.jsonify(message)
    res.status_code = 400
    return res

@app.errorhandler(404)
def not_found(error=False):
    message = {
            'status': 404,
            'message': "Not Found: {:s}".format(flask.request.url)
    }
    res = flask.jsonify(message)
    res.status_code = 404
    return res


if __name__ == "__main__":
    app.run(debug=True)
