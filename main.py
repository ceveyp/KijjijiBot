import multiprocessing
from functions import *
import flask
from flask import request

app = flask.Flask(__name__)
app.config["DEBUG"] = False


@app.route('/add-listings', methods=['POST'])
def add_listings():
    listings = request.json['listings']
    if not db_add_listings(listings):
        return {'error': 1, 'status': 'error', 'message': 'could not add listings'}
    return {'error': 0, 'status': 'start', 'command': 'add_listings'}


@app.route('/remove-listing', methods=['POST'])
def remove_listing():
    listings = request.json['listings']
    if not db_add_removals(listings):
        return {'error': 1, 'status': 'error', 'message': 'could not add removal'}
    return {'error': 0, 'status': 'start', 'command': 'remove_listing'}


if __name__ == '__main__':
    db_init()
    multiprocessing.Process(target=run_listings_bot).start()
    app.run(host="0.0.0.0")
