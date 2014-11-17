'''
Implements a simple, non-reliable "todo-list" API server on localhost.

See README.md for context and more information.

'''
import threading
import argparse
import flask
import json
import random
from functools import wraps

DEFAULT_FAILURE_RATE = 0.01

def get_args():
    parser = argparse.ArgumentParser(description='Non-Reliable Todo-list API server')
    parser.add_argument('-p', '--port', type=int, default=8042,
                        help='Port to accept connections on')
    parser.add_argument('-f', '--failure-rate', type=float, default=DEFAULT_FAILURE_RATE,
                        help='Fraction of time an API call should fail (default {})'.format(DEFAULT_FAILURE_RATE))
    parser.add_argument('-d', '--debug', action='store_true', default=False,
                        help='enable flask debug mode')
    args = parser.parse_args()
    assert (args.failure_rate >= 0.0) and (args.failure_rate <= 1.0), 'Failure rate must be between 0 and 1'
    return args

# in-memory data store
class ItemStore:
    def __init__(self):
        self.items = dict()
        self.id_lock = threading.RLock()
        self.write_lock = threading.RLock()
        self.current_id = 0

    def new_id(self):
        self.id_lock.acquire()
        self.current_id += 1
        _new_id = self.current_id
        self.id_lock.release()
        return _new_id

    def add_item(self, **kwargs):
        item_id = self.new_id()
        info = {'id' : item_id}
        info.update(**kwargs)
        self.write_lock.acquire()
        try:
            assert item_id not in self.items, item_id
            self.items[item_id] = info
        finally:
            self.write_lock.release()
        return info

    def delete_item(self, item_id):
        del self.items[item_id]

    def find_item(self, item_id):
        return self.items[item_id]

    def all_items(self):
        return [{'id': item['id'], 'summary': item['summary']}
                for item in self.items.values()]
    
# API server web app
class ServerApp(flask.Flask):
    @property
    def failure_rate(self):
        return self._failure_rate

    @failure_rate.setter
    def failure_rate(self, failure_rate):
        self._failure_rate = failure_rate

app = ServerApp(__name__)
store = ItemStore()

# URL routing
def unreliable(func):
    @wraps(func)
    def unreliable_func(*a, **kw):
        failure_rate = flask.current_app.failure_rate
        if random.random() < failure_rate:
            raise RuntimeError('Unreliable API Strikes Again!')
        return func(*a, **kw)
    return unreliable_func

@app.route('/items', methods=['GET'])
@unreliable
def list_items():
    return flask.Response(json.dumps(store.all_items()), content_type='application/json')

@app.route('/items', methods=['POST'])
@unreliable
def create_item():
    data = next(flask.request.form.keys())
    params = json.loads(data)
    item = store.add_item(
        summary     = params['summary'],
        description = params['description'],
        )
    return flask.jsonify(**item)

@app.route('/item/<int:item_id>', methods=['GET'])
@unreliable
def describe_item(item_id):
    try:
        return flask.jsonify(store.find_item(item_id))
    except KeyError:
        flask.abort(404)

@app.route('/item/<int:item_id>', methods=['DELETE'])
@unreliable
def delete_item(item_id):
    try:
        store.delete_item(item_id)
    except KeyError:
        flask.abort(404)
    return 'delete {}'.format(item_id)

if __name__ == '__main__':
    args = get_args()
    app.failure_rate = args.failure_rate
    if args.debug:
        app.debug = True
    app.run(port=args.port)
